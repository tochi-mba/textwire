from __future__ import annotations

import pytest

from textwire.protocol.compress import load_dictionary
from textwire.protocol.training import (
    Measurement,
    measure,
    samples_from_text,
    split_held_out,
    train,
)


def test_samples_are_cut_at_blank_lines_near_the_size() -> None:
    text = "\n\n".join("x" * 100 for _ in range(10))
    samples = samples_from_text(text, sample_bytes=250)
    assert [len(sample) for sample in samples] == [202, 202, 202, 202, 202]
    assert b"\n\n".join(samples) == text.encode()


def test_a_block_bigger_than_a_sample_is_one_sample() -> None:
    assert samples_from_text("y" * 500, sample_bytes=100) == [b"y" * 500]


def test_blank_text_has_no_samples() -> None:
    assert samples_from_text("  ") == []


def test_every_fifth_sample_is_held_out() -> None:
    samples = [bytes([n]) for n in range(11)]
    training, held_out = split_held_out(samples)
    assert held_out == [bytes([0]), bytes([5]), bytes([10])]
    assert len(training) == 8


def test_a_trained_dictionary_beats_none_on_similar_text() -> None:
    corpus = [
        f"# Weather for town {n}\n\nToday will be cloudy with sunny spells and a light breeze. "
        f"Temperatures reach {10 + n % 15} degrees. Rain is expected later in town {n}.".encode()
        for n in range(400)
    ]
    training, held_out = split_held_out(corpus)
    dictionary = train(training, 4096)
    result = measure(dictionary, held_out)
    assert result.samples == len(held_out)
    assert result.dictionary_ratio > result.plain_ratio > 1


def test_the_committed_dictionary_measures_better_than_none() -> None:
    sample = (
        b"# Election results\n\nThe Labour Party won the seat with a majority of 4,000 votes, the "
        b"BBC reported on Thursday. Turnout was lower than at the last general election."
    )
    result = measure(load_dictionary().data, [sample])
    assert result.dictionary_bytes < result.plain_bytes


def test_ratios_divide_raw_by_compressed() -> None:
    result = Measurement(samples=1, raw_bytes=100, plain_bytes=50, dictionary_bytes=25)
    assert (result.plain_ratio, result.dictionary_ratio) == (2.0, 4.0)


def test_measuring_nothing_is_an_error() -> None:
    with pytest.raises(ValueError, match="nothing to measure"):
        measure(load_dictionary().data, [])
