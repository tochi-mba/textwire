from __future__ import annotations

from textwire.content.render import HELP_BODY, help_document, search_document
from textwire.content.search import Hit
from textwire.protocol.envelope import Kind


def test_search_results_are_a_numbered_list_of_chips_with_domains() -> None:
    document = search_document(
        "  bbc  weather ",
        [
            Hit(
                "London - BBC Weather", "https://www.bbc.co.uk/weather/2643743", "14-day forecast."
            ),
            Hit("", "https://metoffice.gov.uk/x", ""),
        ],
    )
    assert document.kind is Kind.SEARCH
    assert document.title == "Search: bbc weather"
    assert document.body == (
        "1. London - BBC Weather[1] (bbc.co.uk)\n14-day forecast.\n\n"
        "2. metoffice.gov.uk[2] (metoffice.gov.uk)"
    )
    assert document.links == ("https://www.bbc.co.uk/weather/2643743", "https://metoffice.gov.uk/x")
    assert document.source == "  bbc  weather "


def test_no_results_says_so() -> None:
    document = search_document("zzz", [])
    assert (document.body, document.links) == ("No results.", ())


def test_titles_and_snippets_are_cleaned_so_they_cannot_pose_as_chips() -> None:
    document = search_document(
        "q",
        [
            Hit(
                "Top [10] \N{LEFT DOUBLE QUOTATION MARK}films\N{RIGHT DOUBLE QUOTATION MARK}",
                "https://x.example",
                "Rated \N{REPLACEMENT CHARACTER}[4]\N{EM DASH}\nnew",
            )
        ],
    )
    assert document.body == '1. Top (10) "films"[1] (x.example)\nRated (4)- new'


def test_long_snippets_are_cut_at_a_word() -> None:
    document = search_document("q", [Hit("t", "https://x.example", "word " * 60)])
    snippet = document.body.splitlines()[1]
    assert len(snippet) <= 160
    assert snippet.endswith("word...")


def test_a_snippet_with_no_spaces_is_cut_anywhere() -> None:
    snippet = search_document("q", [Hit("t", "https://x.example", "x" * 300)]).body.splitlines()[1]
    assert snippet == "x" * 157 + "..."


def test_help_is_a_help_document() -> None:
    document = help_document()
    assert (document.kind, document.title, document.body) == (Kind.HELP, "textwire help", HELP_BODY)
    assert "s! weather london" in document.body
