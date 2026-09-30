from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import zstandard
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import REPO_ROOT
from textwire.protocol.compress import (
    DICTIONARY_FILE,
    DICTIONARY_ID,
    MAX_TEXT_BYTES,
    CompressionError,
    Dictionary,
    compress,
    decompress,
    load_dictionary,
)

COMMITTED = REPO_ROOT / "protocol" / "dict" / DICTIONARY_FILE


@pytest.fixture(scope="module")
def dictionary() -> Dictionary:
    return load_dictionary()


def test_the_packaged_dictionary_is_the_committed_one(dictionary: Dictionary) -> None:
    assert dictionary.data == COMMITTED.read_bytes()
    assert dictionary.id == DICTIONARY_ID


def test_the_dictionary_hash_is_recorded_in_its_readme(dictionary: Dictionary) -> None:
    readme = (REPO_ROOT / "protocol" / "dict" / "README.md").read_text(encoding="utf-8")
    assert dictionary.sha256 == hashlib.sha256(COMMITTED.read_bytes()).hexdigest()
    assert f"`{dictionary.sha256}`" in readme


def test_a_dictionary_can_be_loaded_from_a_path(tmp_path: Path) -> None:
    path = tmp_path / "d.zdict"
    path.write_bytes(COMMITTED.read_bytes())
    assert load_dictionary(path) == load_dictionary()


@settings(max_examples=40, deadline=None)
@given(st.text(max_size=3000))
def test_text_survives_a_round_trip(text: str) -> None:
    dictionary = load_dictionary()
    data = text.encode("utf-8")
    assert decompress(compress(data, dictionary), dictionary) == data


def test_compression_is_deterministic(dictionary: Dictionary) -> None:
    data = b"# Village gets its first text-only library\n\nResidents of Dunmore..." * 5
    assert compress(data, dictionary) == compress(data, dictionary)


def test_frames_carry_their_size_and_neither_checksum_nor_dictionary_id(
    dictionary: Dictionary,
) -> None:
    parameters = zstandard.get_frame_parameters(compress(b"hello " * 50, dictionary))
    assert parameters.content_size == 300
    assert parameters.dict_id == 0
    assert not parameters.has_checksum


def test_the_dictionary_makes_english_smaller(dictionary: Dictionary) -> None:
    text = (
        b"The government said on Tuesday that the new rules would come into force next month, "
        b"after a consultation with businesses and the public. Ministers said the changes were "
        b"needed to protect consumers."
    )
    without = zstandard.ZstdCompressor(level=19, write_checksum=False).compress(text)
    assert len(compress(text, dictionary)) < len(without)


def test_data_compressed_with_the_dictionary_needs_it(dictionary: Dictionary) -> None:
    data = compress(b"The government said on Tuesday that the weather " * 3, dictionary)
    with pytest.raises(zstandard.ZstdError):
        zstandard.ZstdDecompressor().decompress(data)


def test_garbage_is_not_a_frame(dictionary: Dictionary) -> None:
    with pytest.raises(CompressionError, match="not a zstd frame"):
        decompress(b"not zstd at all", dictionary)


def test_a_frame_without_a_size_is_refused(dictionary: Dictionary) -> None:
    data = zstandard.ZstdCompressor(write_content_size=False).compress(b"hello")
    with pytest.raises(CompressionError, match="does not declare its size"):
        decompress(data, dictionary)


def test_a_frame_declaring_too_much_is_refused_before_decompressing(
    dictionary: Dictionary,
) -> None:
    data = zstandard.ZstdCompressor().compress(b" " * (MAX_TEXT_BYTES + 1))
    with pytest.raises(CompressionError, match="more than 65536"):
        decompress(data, dictionary)


def test_a_smaller_limit_can_be_set(dictionary: Dictionary) -> None:
    with pytest.raises(CompressionError):
        decompress(compress(b"x" * 100, dictionary), dictionary, max_size=10)


def test_trailing_bytes_after_the_frame_are_refused(dictionary: Dictionary) -> None:
    with pytest.raises(CompressionError, match="corrupt"):
        decompress(compress(b"hello", dictionary) + b"xx", dictionary)


def test_a_corrupt_frame_is_refused(dictionary: Dictionary) -> None:
    data = bytearray(compress(b"hello there, this is a longer line of text" * 4, dictionary))
    data[-3] ^= 0xFF
    with pytest.raises(CompressionError):
        decompress(bytes(data), dictionary)
