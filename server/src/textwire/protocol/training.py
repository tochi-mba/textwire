"""Training and measuring the shared zstd dictionary (ADR-0004).

Pure helpers: turning documents into page-sized samples, splitting off a held-out set,
training, and measuring what a dictionary saves. ``server/scripts/train_dictionary.py``
drives them over a corpus fetched from the real web; ``protocol/dict/README.md`` records the
result of the run that produced the committed dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zstandard

from textwire.protocol.compress import DICTIONARY_ID, LEVEL, Dictionary, compress

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

#: About what one default page (12 frames) holds before compression.
SAMPLE_BYTES = 4096
#: Every fifth sample is held out to measure the dictionary on text it never saw.
HOLD_OUT_EVERY = 5


def samples_from_text(text: str, sample_bytes: int = SAMPLE_BYTES) -> list[bytes]:
    """Page-sized samples of ``text``, cut at blank lines where possible."""
    samples: list[bytes] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if current and len(candidate.encode("utf-8")) > sample_bytes:
            samples.append(current.encode("utf-8"))
            current = block
        else:
            current = candidate
    if current.strip():
        samples.append(current.encode("utf-8"))
    return samples


def split_held_out(samples: Sequence[bytes]) -> tuple[list[bytes], list[bytes]]:
    """``(training, held_out)``: every fifth sample is held out, deterministically."""
    training = [sample for index, sample in enumerate(samples) if index % HOLD_OUT_EVERY]
    held_out = [sample for index, sample in enumerate(samples) if not index % HOLD_OUT_EVERY]
    return training, held_out


def train(samples: Sequence[bytes], size: int) -> bytes:
    """A dictionary of ``size`` bytes trained on ``samples`` with tuned parameters."""
    trained = zstandard.train_dictionary(
        size, list(samples), dict_id=DICTIONARY_ID, level=LEVEL, threads=-1
    )
    return trained.as_bytes()


@dataclass(frozen=True, slots=True)
class Measurement:
    """What compressing a set of samples costs, with and without a dictionary."""

    samples: int
    raw_bytes: int
    plain_bytes: int
    dictionary_bytes: int

    @property
    def plain_ratio(self) -> float:
        """Raw size over size compressed without the dictionary."""
        return self.raw_bytes / self.plain_bytes

    @property
    def dictionary_ratio(self) -> float:
        """Raw size over size compressed with the dictionary."""
        return self.raw_bytes / self.dictionary_bytes


def measure(dictionary: bytes, samples: Iterable[bytes]) -> Measurement:
    """Compress every sample both ways at the production level and add up the sizes."""
    plain = zstandard.ZstdCompressor(level=LEVEL, write_checksum=False, write_content_size=True)
    shared = Dictionary(DICTIONARY_ID, dictionary)
    count = raw = without = with_dictionary = 0
    for sample in samples:
        count += 1
        raw += len(sample)
        without += len(plain.compress(sample))
        with_dictionary += len(compress(sample, shared))
    if count == 0:
        msg = "nothing to measure"
        raise ValueError(msg)
    return Measurement(count, raw, without, with_dictionary)
