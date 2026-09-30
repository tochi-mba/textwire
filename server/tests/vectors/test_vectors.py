from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from textwire.cli.main import main
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.compress import load_dictionary
from textwire.protocol.envelope import Codec, Envelope, Kind, pack_envelope, unpack_envelope
from textwire.protocol.frames import Frame, FrameError, FrameType, decode_frame, encode_frame
from textwire.protocol.requests import (
    Request,
    RequestError,
    Verb,
    format_request,
    parse_request,
)
from textwire.vectors import check, find_repo_root, write
from textwire.vectors.cases import envelope_fault, frame_fault, request_error

VECTORS = REPO_ROOT / "protocol" / "vectors"


def _cases(folder: str) -> list[tuple[str, dict[str, object]]]:
    return [
        (path.stem, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((VECTORS / folder).glob("*.json"))
    ]


def test_the_committed_vectors_match_the_reference() -> None:
    assert check(REPO_ROOT) == []


@pytest.mark.parametrize(("name", "case"), _cases("frames"))
def test_frame_vectors(name: str, case: dict[str, object]) -> None:
    text = str(case["text"])
    if case["fault"] is None:
        spec = case["frame"]
        assert isinstance(spec, dict)
        frame = Frame(
            tag=spec["tag"],
            seq=spec["seq"],
            total=spec["total"],
            body=bytes.fromhex(spec["body_hex"]),
            type=FrameType(spec["type"]),
        )
        assert decode_frame(text) == frame
        assert encode_frame(frame, Alphabet(str(case["alphabet"]))) == text.strip()
    else:
        with pytest.raises(FrameError) as caught:
            decode_frame(text)
        assert caught.value.fault.value == case["fault"], name


@pytest.mark.parametrize(("name", "case"), _cases("requests"))
def test_request_vectors(name: str, case: dict[str, object]) -> None:
    text = str(case["text"])
    if case["error"] is None:
        spec = case["request"]
        assert isinstance(spec, dict)
        request = Request(**{**spec, "verb": Verb(spec["verb"]), "seqs": tuple(spec["seqs"])})
        assert parse_request(text) == request
        assert format_request(request) == case["canonical"]
    else:
        with pytest.raises(RequestError, match=f"^{case['error']}$"):
            parse_request(text)


@pytest.mark.parametrize(("name", "case"), _cases("envelopes"))
def test_envelope_vectors(name: str, case: dict[str, object]) -> None:
    dictionary = load_dictionary()
    payload = bytes.fromhex(str(case["payload_hex"]))
    if case["fault"] is None:
        spec = case["envelope"]
        assert isinstance(spec, dict)
        envelope = Envelope(Kind(spec["kind"]), spec["page"], spec["pages"], spec["text"])
        assert unpack_envelope(payload, dictionary) == envelope
        assert pack_envelope(envelope, dictionary, Codec(int(str(case["codec"])))) == payload
    else:
        assert envelope_fault(payload, dictionary) == case["fault"], name


def test_the_document_vectors_decode_to_their_pages() -> None:
    dictionary = load_dictionary()
    documents = _cases("documents")
    assert len(documents) == 4
    for _name, case in documents:
        pages = case["pages"]
        assert isinstance(pages, dict)
        for entries in pages.values():
            for number, entry in enumerate(entries, 1):
                envelope = unpack_envelope(bytes.fromhex(entry["payload_hex"]), dictionary)
                assert (envelope.text, envelope.page, envelope.pages) == (
                    entry["text"],
                    number,
                    len(entries),
                )


def test_ids_name_the_committed_dictionary() -> None:
    ids = json.loads((VECTORS / "ids.json").read_text(encoding="utf-8"))
    assert ids["dictionary"]["sha256"] == load_dictionary().sha256
    assert ids["frame"]["faults"][0] == "encoding"
    assert ids["frame"]["alphabets"]["z85g"] == {
        "marker": ".",
        "frame_bytes": 127,
        "body_bytes": 121,
    }


def test_rejection_helpers_refuse_inputs_that_are_valid() -> None:
    frame = encode_frame(Frame(tag=1, seq=0, total=1, body=b""))
    with pytest.raises(AssertionError, match="decodes"):
        frame_fault(frame)
    with pytest.raises(AssertionError, match="parses"):
        request_error("h")
    dictionary = load_dictionary()
    payload = pack_envelope(Envelope(Kind.HELP, 1, 1, "x"), dictionary)
    with pytest.raises(AssertionError, match="unpacks"):
        envelope_fault(payload, dictionary)


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A copy of just what the vectors need: the marker, the fixtures and the vectors."""
    (tmp_path / "protocol").mkdir()
    shutil.copy(REPO_ROOT / "protocol" / "PROTOCOL.md", tmp_path / "protocol" / "PROTOCOL.md")
    shutil.copytree(REPO_ROOT / "protocol" / "fixtures", tmp_path / "protocol" / "fixtures")
    shutil.copytree(VECTORS, tmp_path / "protocol" / "vectors")
    return tmp_path


def test_check_reports_changed_missing_and_unexpected_files(scratch_repo: Path) -> None:
    folder = scratch_repo / "protocol" / "vectors"
    (folder / "ids.json").write_text("{}\n", encoding="utf-8")
    (folder / "frames" / "b64-data-empty.json").unlink()
    (folder / "frames" / "stray.json").write_text("{}\n", encoding="utf-8")
    assert check(scratch_repo) == [
        "missing: frames/b64-data-empty.json",
        "unexpected: frames/stray.json",
        "changed: ids.json",
    ]


def test_write_restores_the_reference_and_says_what_changed(scratch_repo: Path) -> None:
    folder = scratch_repo / "protocol" / "vectors"
    (folder / "ids.json").write_text("{}\n", encoding="utf-8")
    assert write(scratch_repo) == ["changed: ids.json"]
    assert check(scratch_repo) == []


def test_the_repository_root_is_found_from_inside_it() -> None:
    assert find_repo_root(REPO_ROOT / "server" / "src") == REPO_ROOT
    assert find_repo_root(REPO_ROOT) == REPO_ROOT


def test_outside_a_checkout_there_is_no_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not inside a textwire checkout"):
        find_repo_root(tmp_path)


def test_the_cli_checks_and_regenerates(
    scratch_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["vectors", "check", "--root", str(scratch_repo)]) == 0
    (scratch_repo / "protocol" / "vectors" / "ids.json").write_text("{}\n", encoding="utf-8")
    assert main(["vectors", "check", "--root", str(scratch_repo)]) == 1
    assert "changed: ids.json" in capsys.readouterr().out
    monkeypatch.chdir(scratch_repo / "protocol")
    assert main(["vectors", "regen"]) == 0
    assert "1 file(s) changed" in capsys.readouterr().out
    assert main(["vectors", "check"]) == 0
