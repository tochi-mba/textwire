"""Fixtures for the content pipeline: the recorded pages and searches in protocol/fixtures."""

from __future__ import annotations

import pytest

from tests.conftest import REPO_ROOT
from textwire.content.fakes import FakeFetcher, FakeSearchProvider, load_fixtures

FIXTURES = REPO_ROOT / "protocol" / "fixtures"
ARTICLE = "https://dunmore-gazette.example/news/text-only-library"
WIKIPEDIA = "https://en.wikipedia.org/wiki/SMS_gateway"
NOTES = "https://notes.example/reading-by-text.txt"


@pytest.fixture
def recorded() -> tuple[FakeFetcher, FakeSearchProvider]:
    """Fakes that serve the recorded fixtures."""
    return load_fixtures(FIXTURES)
