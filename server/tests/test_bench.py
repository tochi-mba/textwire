"""The performance baseline: what it measures, how it compares, and that it is current."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import REPO_ROOT
from textwire import bench
from textwire.cli import bench as bench_cli
from textwire.cli.main import main

FAKE: dict[str, Any] = {
    "version": "0.1.0",
    "machine": {"python": "3.12.10", "system": "Windows 11", "processor": "AMD64"},
    "cost": {
        "dictionary": {"sha256": "ab", "bytes": 1},
        "documents": {"notes": {"b64/12": {"pages": 2, "sms_total": 9, "ratio": 3.0, "fill": 0.9}}},
        "sms_total": {"b64/12": 9},
    },
    "speed": {"request_page_ms": 10.0, "extract_all_fixtures_ms": 100.0},
}


def _changed(**edits: Any) -> dict[str, Any]:
    """A copy of FAKE with the named measurements replaced: ``_changed(sms_total=8)``."""
    result: dict[str, Any] = json.loads(json.dumps(FAKE))
    cut = result["cost"]["documents"]["notes"]["b64/12"]
    for key, value in edits.items():
        if key in cut:
            cut[key] = value
        elif key in result["speed"]:
            result["speed"][key] = value
    return result


def test_the_committed_baseline_says_what_the_code_sends() -> None:
    """Like the vector check: a change in SMS per page must come with a new baseline."""
    recorded = bench.load(REPO_ROOT / bench.BASELINE)
    assert recorded["cost"] == bench.cost(REPO_ROOT)


def test_cost_counts_every_fixture_at_every_cut() -> None:
    cost = bench.cost(REPO_ROOT)
    assert set(cost["documents"]) == {
        "dunmore-gazette-example",
        "en-wikipedia-org",
        "notes-example",
        "search-bbc-weather-london",
    }
    for cuts in cost["documents"].values():
        assert set(cuts) == {"b64/12", "b64/4", "z85g/12", "plain/4"}
        for cut in ("b64/12", "b64/4", "z85g/12"):
            numbers = cuts[cut]
            assert numbers["sms_first_page"] <= numbers["sms_total"]
            assert 0 < numbers["fill"] <= 1
            assert numbers["ratio"] > 1
        # A smaller page is never fewer pages.
        assert cuts["b64/4"]["pages"] >= cuts["b64/12"]["pages"]
    totals = cost["sms_total"]
    # The denser alphabet never needs more SMS for the same pages.
    assert totals["z85g/12"] <= totals["b64/12"]
    assert len(cost["dictionary"]["sha256"]) == 64
    assert cost["dictionary"]["bytes"] > 0


def test_speed_times_every_stage() -> None:
    speed = bench.speed(REPO_ROOT, repeats=1)
    assert set(speed) == {
        "extract_all_fixtures_ms",
        "paginate_all_fixtures_ms",
        "compress_article_ms",
        "decompress_article_ms",
        "encode_page_frames_ms",
        "decode_page_frames_ms",
        "request_page_ms",
        "request_search_ms",
    }
    assert all(value >= 0 for value in speed.values())


def test_measure_records_the_machine_beside_both_halves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bench, "speed", lambda _root, _repeats: {"x_ms": 1.0})
    result = bench.measure(REPO_ROOT, repeats=1)
    assert set(result) == {"version", "machine", "cost", "speed"}
    assert set(result["machine"]) == {"python", "system", "processor"}
    assert result["speed"] == {"x_ms": 1.0}


def test_timed_is_the_median() -> None:
    clock = iter([0, 5_000_000, 0, 1_000_000, 0, 3_000_000])
    calls: list[int] = []
    assert bench.timed(lambda: calls.append(1), 3, clock=lambda: next(clock)) == 3.0
    assert len(calls) == 3


def test_an_unchanged_result_has_no_changes() -> None:
    assert bench.compare(FAKE, _changed()) == []


@pytest.mark.parametrize(
    ("edit", "metric", "worse"),
    [
        ({"sms_total": 10}, "cost/documents/notes/b64/12/sms_total", True),
        ({"sms_total": 8}, "cost/documents/notes/b64/12/sms_total", False),
        ({"ratio": 2.5}, "cost/documents/notes/b64/12/ratio", True),
        ({"fill": 0.95}, "cost/documents/notes/b64/12/fill", False),
        ({"request_page_ms": 16.0}, "speed/request_page_ms", True),
        ({"request_page_ms": 4.0}, "speed/request_page_ms", False),
    ],
)
def test_each_change_says_which_way_it_went(
    edit: dict[str, float], metric: str, *, worse: bool
) -> None:
    [change] = bench.compare(FAKE, _changed(**edit))
    assert (change.metric, change.worse) == (metric, worse)


def test_timings_within_the_tolerance_are_not_changes() -> None:
    assert bench.compare(FAKE, _changed(request_page_ms=14.9, extract_all_fixtures_ms=60.0)) == []


def test_metrics_only_one_side_has_are_not_compared() -> None:
    after = _changed()
    after["cost"]["documents"]["new"] = {"b64/12": {"sms_total": 3}}
    after["speed"]["new_ms"] = 1.0
    del after["speed"]["extract_all_fixtures_ms"]
    assert bench.compare(FAKE, after) == []


def test_text_and_switches_in_a_result_are_not_metrics() -> None:
    before = _changed()
    after = _changed()
    before["cost"]["documents"]["notes"]["b64/12"]["label"] = "a"
    after["cost"]["documents"]["notes"]["b64/12"]["label"] = "b"
    after["cost"]["documents"]["notes"]["b64/12"]["flag"] = True
    assert bench.compare(before, after) == []


def test_a_change_reads_as_one_line() -> None:
    assert (
        bench.Change("cost/x/sms_total", 9, 8, worse=False).describe()
        == "cost/x/sms_total: 9 -> 8 (better)"
    )
    assert (
        bench.Change("speed/y_ms", 1.5, 3.25, worse=True).describe()
        == "speed/y_ms: 1.5 -> 3.25 (worse)"
    )


def test_a_result_is_saved_readably_and_loads_back(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "baseline.json"
    bench.save(FAKE, path)
    assert bench.load(path) == FAKE
    assert path.read_bytes().startswith(b'{\n  "cost"')
    assert b"\r" not in path.read_bytes()


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose measurements are FAKE, so the command runs in a moment."""
    monkeypatch.setattr(bench_cli, "measure", lambda _root, _repeats: json.loads(json.dumps(FAKE)))
    return tmp_path


def test_the_command_asks_for_a_baseline_when_there_is_none(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bench_cli.bench(root) == 1
    out = capsys.readouterr().out
    assert "no baseline at benchmarks/baseline.json; run `make bench-record` first" in out
    assert "b64/12" in out


def test_the_command_records_and_then_finds_nothing_changed(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bench_cli.bench(root, record=True) == 0
    assert bench.load(root / bench.BASELINE) == FAKE
    assert "recorded benchmarks/baseline.json" in capsys.readouterr().out
    assert bench_cli.bench(root) == 0
    out = capsys.readouterr().out
    assert "against the baseline recorded with textwire 0.1.0 on Windows 11, Python 3.12.10" in out
    assert "(baseline 9)" in out
    assert "(baseline 10.000)" in out
    assert "no change in cost, and every timing within tolerance" in out


def test_the_command_fails_when_a_page_costs_more(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bench.save(_changed(sms_total=8), root / bench.BASELINE)
    assert bench_cli.bench(root) == 1
    out = capsys.readouterr().out
    assert "cost/documents/notes/b64/12/sms_total: 8 -> 9 (worse)" in out
    assert "1 cost metric(s) got worse: pages now take more SMS." in out


def test_the_command_passes_an_improvement_and_says_to_record_it(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bench.save(_changed(sms_total=10, request_page_ms=1.0), root / bench.BASELINE)
    assert bench_cli.bench(root) == 0
    out = capsys.readouterr().out
    assert "(better)" in out
    assert "speed/request_page_ms: 1 -> 10 (worse)" in out
    assert "record the improvement with `make bench-record`" in out


def test_the_cli_runs_bench_with_its_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, bool, int]] = []

    def fake(root: Path, *, record: bool, repeats: int) -> int:
        calls.append((root, record, repeats))
        return 0

    monkeypatch.setattr("textwire.cli.main.bench", fake)
    assert main(["bench", "--root", str(tmp_path), "--record", "--repeats", "3"]) == 0
    assert main(["bench", "--root", str(tmp_path)]) == 0
    monkeypatch.chdir(REPO_ROOT / "server")
    assert main(["bench"]) == 0
    assert calls == [(tmp_path, True, 3), (tmp_path, False, 15), (REPO_ROOT, False, 15)]
