from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.content.conftest import ARTICLE, WIKIPEDIA
from textwire.content.document import Document
from textwire.content.extract import extract_document
from textwire.content.fakes import FakeFetcher, FakeSearchProvider
from textwire.content.pages import (
    TITLE_CHARS,
    _paginate,
    capacity,
    page_count,
    page_payload,
    paginate,
    plain_document_pages,
    title_line,
)
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.compress import Dictionary, load_dictionary
from textwire.protocol.envelope import ENVELOPE_BYTES, Kind, unpack_envelope
from textwire.protocol.frames import BODY_BYTES, MAX_FRAMES, body_bytes, split_payload


@pytest.fixture(scope="module")
def dictionary() -> Dictionary:
    return load_dictionary()


def _doc(body: str, title: str = "A title") -> Document:
    return Document(kind=Kind.PAGE, title=title, body=body)


def test_capacity_is_frames_of_body_less_the_envelope() -> None:
    assert capacity(12) == 12 * BODY_BYTES - ENVELOPE_BYTES
    assert capacity(1) == 110
    assert capacity(1, Alphabet.Z85G) == 117


async def test_the_denser_alphabet_needs_fewer_frames_and_pages(
    recorded: tuple[FakeFetcher, FakeSearchProvider], dictionary: Dictionary
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(WIKIPEDIA))
    dense = page_count(document, dictionary, 4, Alphabet.Z85G)
    assert dense <= page_count(document, dictionary, 4)
    for number in range(1, dense + 1):
        payload = page_payload(document, dictionary, 4, number, Alphabet.Z85G)
        assert len(split_payload(0, payload, Alphabet.Z85G)) <= 4
        assert len(payload) <= 4 * body_bytes(Alphabet.Z85G)


def test_titles_are_one_line_and_at_most_sixty_characters() -> None:
    assert title_line("  Two\n words ", 200) == "# Two words"
    long = title_line("x" * 100, 200)
    assert long == "# " + "x" * (TITLE_CHARS - 3) + "..."


def test_titles_also_fit_a_byte_budget() -> None:
    line = title_line("\N{SNOWMAN}" * 30, 20)
    assert len(line.encode()) <= 20
    assert line.endswith("...")


def test_a_short_document_is_one_page_starting_with_its_title(dictionary: Dictionary) -> None:
    assert paginate(_doc("Hello there."), dictionary, 12) == ("# A title\n\nHello there.",)


def test_a_document_with_no_body_is_one_title_page(dictionary: Dictionary) -> None:
    assert paginate(_doc(""), dictionary, 12) == ("# A title",)


async def test_every_page_of_a_real_article_fits_its_frames(
    recorded: tuple[FakeFetcher, FakeSearchProvider], dictionary: Dictionary
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(WIKIPEDIA))
    for size in (1, 4, 12, 40):
        pages = paginate(document, dictionary, size)
        assert all(page.startswith("# SMS gateway") for page in pages)
        for number in range(1, len(pages) + 1):
            payload = page_payload(document, dictionary, size, number)
            assert len(split_payload(0, payload)) <= size
            envelope = unpack_envelope(payload, dictionary)
            assert (envelope.page, envelope.pages) == (number, len(pages))
        assert page_count(document, dictionary, size) == len(pages)
    assert page_count(document, dictionary, 1) > page_count(document, dictionary, 12)


async def test_no_text_is_lost_or_repeated(
    recorded: tuple[FakeFetcher, FakeSearchProvider], dictionary: Dictionary
) -> None:
    fetcher, _ = recorded
    document = extract_document(await fetcher.fetch(ARTICLE))
    pages = paginate(document, dictionary, 2)
    head = "# " + document.title + "\n\n"
    rejoined = "\n\n".join(page.removeprefix(head) for page in pages)
    assert rejoined.split() == document.body.split()


def test_an_enormous_paragraph_is_split_at_sentences(dictionary: Dictionary) -> None:
    body = " ".join(f"Sentence {n} says something new about item {n * 7}." for n in range(400))
    pages = paginate(_doc(body), dictionary, 2)
    assert len(pages) > 1
    assert all(page.rstrip().endswith(".") for page in pages)


def test_a_long_line_list_is_split_between_items(dictionary: Dictionary) -> None:
    body = "\n".join(f"- Item {n} with a few words of its own, number {n * 13}" for n in range(300))
    pages = paginate(_doc(body), dictionary, 2)
    assert len(pages) > 1
    assert all(line.startswith(("# ", "- ")) for page in pages for line in page.split("\n") if line)


def test_a_sentence_too_long_for_a_page_is_split_at_spaces(dictionary: Dictionary) -> None:
    body = " ".join(f"w{n:04d}" for n in range(3000))
    document = _doc(body)
    pages = paginate(document, dictionary, 1)
    for number in range(1, len(pages) + 1):
        assert len(page_payload(document, dictionary, 1, number)) <= BODY_BYTES
    assert "w0000" in pages[0]
    assert all(page.rsplit(" ", 1)[-1].startswith("w") for page in pages[:-1])


def test_a_word_too_long_for_a_page_is_cut_anywhere(dictionary: Dictionary) -> None:
    body = "".join(chr(0x4E00 + n) for n in range(3000))
    pages = paginate(_doc(body, title="t"), dictionary, 1)
    assert len(pages) > 1
    assert "".join(page.removeprefix("# t\n\n") for page in pages) == body


def test_a_document_is_cut_at_255_pages(dictionary: Dictionary) -> None:
    varied = "".join(chr(0x4E00 + (n * 7919) % 20000) for n in range(16000))
    body = "\n\n".join(varied[start : start + 40] for start in range(0, len(varied), 40))
    assert len(paginate(_doc(body), dictionary, 1)) == MAX_FRAMES


def test_pages_outside_the_document_do_not_exist(dictionary: Dictionary) -> None:
    with pytest.raises(IndexError, match="page 2 of 1"):
        page_payload(_doc("x"), dictionary, 12, 2)
    with pytest.raises(IndexError):
        page_payload(_doc("x"), dictionary, 12, 0)


def test_pagination_is_repeatable(dictionary: Dictionary) -> None:
    document = _doc("\n\n".join(f"Paragraph {n}." for n in range(200)))
    assert paginate(document, dictionary, 3) == _paginate(
        document, dictionary, 3, Alphabet.BASE64URL
    )


@settings(max_examples=25, deadline=None)
@given(
    st.lists(st.text(min_size=1, max_size=600), min_size=1, max_size=30),
    st.integers(1, 20),
)
def test_any_text_paginates_into_pages_that_fit(paragraphs: list[str], size: int) -> None:
    dictionary = load_dictionary()
    document = _doc("\n\n".join(paragraphs))
    pages = paginate(document, dictionary, size)
    for number in range(1, len(pages) + 1):
        assert len(page_payload(document, dictionary, size, number)) <= size * BODY_BYTES


def test_plain_pages_start_with_the_title() -> None:
    pages = plain_document_pages(_doc("Hello."), 4)
    assert pages == [["# A title\n\nHello."]]


def test_plain_pages_of_an_empty_document_hold_the_title() -> None:
    assert plain_document_pages(_doc(""), 2) == [["# A title"]]
