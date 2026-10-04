"""``textwire bench``: measure, compare with the committed baseline, or record a new one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textwire.bench import BASELINE, compare, load, measure, save

if TYPE_CHECKING:
    from pathlib import Path


def bench(root: Path, *, record: bool = False, repeats: int = 15) -> int:
    """Print this checkout's numbers against the baseline; 1 if a page now costs more SMS.

    Slower timings are reported but do not fail: they move with the machine. ``record``
    writes the numbers as the new baseline instead of comparing.
    """
    result = measure(root, repeats)
    path = root / BASELINE
    if record:
        save(result, path)
        print(f"recorded {path.relative_to(root).as_posix()}")
        _summary(result)
        return 0
    if not path.is_file():
        print(f"no baseline at {path.relative_to(root).as_posix()}; run `make bench-record` first")
        _summary(result)
        return 1
    baseline = load(path)
    machine = baseline["machine"]
    print(
        f"against the baseline recorded with textwire {baseline['version']} on "
        f"{machine['system']}, Python {machine['python']}"
    )
    _summary(result, baseline)
    changes = compare(baseline, result)
    for change in changes:
        print(f"  {change.describe()}")
    worse_cost = [c for c in changes if c.worse and c.metric.startswith("cost/")]
    if worse_cost:
        print(f"{len(worse_cost)} cost metric(s) got worse: pages now take more SMS.")
        return 1
    if not changes:
        print("no change in cost, and every timing within tolerance")
    else:
        print("record the improvement with `make bench-record` and commit benchmarks/baseline.json")
    return 0


def _summary(result: dict[str, Any], baseline: dict[str, Any] | None = None) -> None:
    """SMS for every fixture at each cut, and each timing, beside the baseline's if given."""
    old_cost: dict[str, Any] = baseline["cost"] if baseline else {}
    old_speed: dict[str, float] = baseline["speed"] if baseline else {}
    print("SMS for every fixture document:")
    for cut, total in result["cost"]["sms_total"].items():
        was = old_cost.get("sms_total", {}).get(cut)
        print(f"  {cut:<10} {total:>5}" + (f"   (baseline {was})" if was is not None else ""))
    print("Median milliseconds:")
    for name, value in result["speed"].items():
        was = old_speed.get(name)
        print(
            f"  {name:<26} {value:>10.3f}" + (f"   (baseline {was:.3f})" if was is not None else "")
        )
