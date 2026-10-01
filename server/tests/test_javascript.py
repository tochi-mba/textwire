"""The two browser scripts are tested in Node; this runs those tests as part of the suite.

The dashboard's script is cut out of the page the server serves and the site's is read from
``site/app.js``, so what is tested is what ships. Node is on every CI runner; a machine
without it skips these locally and says so, and CI never skips.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from textwire.api.dashboard import DASHBOARD_HTML

JS = Path(__file__).parent / "js"
_SCRIPT = re.compile(r"<script>(.*?)</script>", re.DOTALL)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("Node is required in CI to test the browser scripts.")
        pytest.skip("Node is not installed; the browser scripts' tests need it.")
    return node


def _run(test: str, variable: str, script: Path) -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments
        [_node(), "--test", str(JS / test)],
        env={**os.environ, variable: str(script)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_dashboard_has_one_inline_script_and_loads_nothing() -> None:
    assert len(_SCRIPT.findall(DASHBOARD_HTML)) == 1
    assert "<script src" not in DASHBOARD_HTML
    assert "<link" not in DASHBOARD_HTML


def test_the_dashboard_script(tmp_path: Path) -> None:
    [script] = _SCRIPT.findall(DASHBOARD_HTML)
    path = tmp_path / "dashboard.js"
    path.write_text(script, encoding="utf-8")
    _run("dashboard.test.mjs", "TEXTWIRE_DASHBOARD_SCRIPT", path)


def test_the_site_script() -> None:
    _run("site.test.mjs", "TEXTWIRE_SITE_SCRIPT", REPO_ROOT / "site" / "app.js")


def test_every_element_the_dashboard_script_reads_is_on_the_page() -> None:
    [script] = _SCRIPT.findall(DASHBOARD_HTML)
    page = DASHBOARD_HTML.replace(script, "")
    wanted = set(re.findall(r'\$\("([\w-]+)"\)', script))
    assert wanted
    assert sorted(name for name in wanted if f'id="{name}"' not in page) == []


def test_a_machine_without_node_skips_locally_and_fails_in_ci(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _node()
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception):
        _node()
