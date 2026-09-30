from __future__ import annotations

import pytest

from textwire.content.markdown import LinkTable, split_title, to_document_text

BASE = "https://news.example/story/one"


def _doc(markdown: str) -> str:
    return to_document_text(markdown, BASE)[0]


def test_links_become_numbered_chips_in_reading_order() -> None:
    body, links = to_document_text(
        "Read [the report](https://a.example/r) and [the reply](https://b.example/).", BASE
    )
    assert body == "Read the report[1] and the reply[2]."
    assert links == ("https://a.example/r", "https://b.example/")


def test_a_repeated_url_keeps_its_first_number() -> None:
    body, links = to_document_text("[a](https://x.example) then [b](https://x.example)", BASE)
    assert body == "a[1] then b[1]"
    assert links == ("https://x.example",)


def test_relative_links_resolve_against_the_page() -> None:
    _, links = to_document_text("[more](../two) [top](/)", BASE)
    assert links == ("https://news.example/two", "https://news.example/")


@pytest.mark.parametrize(
    "link",
    [
        "[mail us](mailto:a@b.example)",
        "[call](tel:+447700900123)",
        "[x](javascript:void(0))",
        "[jump](#section)",
        "[same page](https://news.example/story/one#part)",
        "[odd](ftp://files.example/a)",
        "[odd](//)",
    ],
)
def test_links_that_cannot_be_followed_become_plain_text(link: str) -> None:
    body, links = to_document_text(f"Please {link} today.", BASE)
    assert links == ()
    assert "[" not in body


def test_an_unusual_scheme_after_resolution_is_plain_text() -> None:
    body, links = to_document_text("[x](ssh://host.example/)", BASE)
    assert (body, links) == ("x", ())


@pytest.mark.parametrize(
    "citation",
    [
        r"<sup>[\[1\]](https://en.wikipedia.org#cite_note-1)</sup>",
        r"[\[a\]](https://en.wikipedia.org#cite_note-3)",
        "[[12]](#cite)",
        "[citation needed]",
        "[3]",
        "[edit]",
    ],
)
def test_citations_disappear(citation: str) -> None:
    assert _doc(f"Fact.{citation} Next.") == "Fact. Next."


def test_links_with_empty_text_disappear() -> None:
    body, links = to_document_text("A [](https://x.example) B", BASE)
    assert (body, links) == ("A B", ())


def test_images_disappear() -> None:
    assert _doc("Look ![a cat](https://img.example/cat.jpg) here") == "Look here"


def test_urls_with_parentheses_and_titles_are_understood() -> None:
    body, links = to_document_text(
        '[Mercury](https://en.wikipedia.org/wiki/Mercury_(planet) "the planet")', BASE
    )
    assert body == "Mercury[1]"
    assert links == ("https://en.wikipedia.org/wiki/Mercury_(planet)",)


def test_angle_bracketed_urls_are_understood() -> None:
    _, links = to_document_text("[x](<https://x.example/a b>)", BASE)
    assert links == ("https://x.example/a b",)


def test_links_stop_at_sixty_and_the_rest_are_plain_text() -> None:
    markdown = " ".join(f"[l{n}](https://x.example/{n})" for n in range(65))
    body, links = to_document_text(markdown, BASE)
    assert len(links) == 60
    assert body.endswith("l59[60] l60 l61 l62 l63 l64")


def test_escapes_are_removed() -> None:
    assert _doc(r"1\. not a list \*really\* \[sic\]") == "1. not a list *really* [sic]"


def test_bold_markers_are_removed() -> None:
    assert _doc("**Short Message Service** (__SMS__)") == "Short Message Service (SMS)"


def test_headings_flatten_and_stand_alone() -> None:
    assert _doc("# Title\ntext\n### Deep ##\nmore") == "## Title\n\ntext\n\n## Deep\n\nmore"


def test_list_markers_normalise() -> None:
    assert _doc("* a\n  + b\n1) c\n2. d") == "- a\n- b\n1. c\n2. d"


def test_rules_fences_and_table_separators_disappear() -> None:
    markdown = "a\n\n---\n\n```\ncode\n```\n\n| x | y |\n|---|:--:|\n| 1 | 2 |"
    assert _doc(markdown) == "a\n\ncode\n\n| x | y |\n| 1 | 2 |"


def test_typography_and_invisible_characters_are_simplified() -> None:
    markdown = (
        "\N{LEFT DOUBLE QUOTATION MARK}Hi\N{RIGHT DOUBLE QUOTATION MARK}\N{EM DASH}"
        "a\N{ZERO WIDTH SPACE}b\N{SOFT HYPHEN}c\N{REPLACEMENT CHARACTER}"
    )
    assert _doc(markdown) == '"Hi"-abc'


def test_inline_html_tags_disappear_but_their_text_stays() -> None:
    assert _doc("E = mc<sup>2</sup> and <b>bold</b><br>line") == "E = mc2 and boldline"


def test_short_lines_that_repeat_like_boilerplate_disappear() -> None:
    markdown = "- Share\n- Story one\n- Share\n- Story two\n- Share\n\n## Share\n\nShare this"
    assert _doc(markdown) == "- Story one\n- Story two\n\n## Share\n\nShare this"


def test_double_spaces_collapse_and_carriage_returns_go() -> None:
    assert _doc("a  b\r\nc\rd") == "a b\nc\nd"


def test_blank_runs_collapse_to_one_blank_line() -> None:
    assert _doc("a\n\n\n\n\nb\n") == "a\n\nb"


def test_a_leading_heading_is_the_title() -> None:
    assert split_title("## SMS\n\nbody\n\nmore") == ("SMS", "body\n\nmore")


def test_without_a_leading_heading_there_is_no_title() -> None:
    assert split_title("body\n\n## Later") == (None, "body\n\n## Later")


def test_a_link_table_can_have_a_smaller_limit() -> None:
    table = LinkTable(BASE, limit=1)
    assert table.urls == ()
