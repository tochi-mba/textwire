"""zstd with the shared, trained dictionary (PROTOCOL.md section 4, ADR-0004).

The dictionary ships inside this package (``protocol/data/textwire-v1.zdict``) as a byte-for-
byte copy of ``protocol/dict/textwire-v1.zdict``; a test keeps the two identical. Its id is
the envelope's codec number, so retraining it means a new file and a new id, never an edit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cached_property
from importlib import resources
from typing import TYPE_CHECKING

import zstandard

if TYPE_CHECKING:
    from pathlib import Path

DICTIONARY_ID = 1
DICTIONARY_FILE = "textwire-v1.zdict"
LEVEL = 19
#: The most text a compressed page may expand to. Pages are a few kilobytes; this refuses a
#: decompression bomb without refusing anything real.
MAX_TEXT_BYTES = 65536


class CompressionError(ValueError):
    """Bytes that are not a zstd frame this dictionary can decode within the size limit."""


@dataclass(frozen=True)
class Dictionary:
    """A zstd dictionary and the codec id it is known by."""

    id: int
    data: bytes

    @cached_property
    def sha256(self) -> str:
        """The dictionary's SHA-256, as lower-case hex."""
        return hashlib.sha256(self.data).hexdigest()

    @cached_property
    def zstd(self) -> zstandard.ZstdCompressionDict:
        """The dictionary in the form the zstd bindings take, digested once for level 19."""
        digested = zstandard.ZstdCompressionDict(self.data, dict_type=zstandard.DICT_TYPE_FULLDICT)
        digested.precompute_compress(level=LEVEL)
        return digested

    @cached_property
    def compressor(self) -> zstandard.ZstdCompressor:
        """A compressor bound to this dictionary.

        Built once: digesting a 110 KiB dictionary costs tens of milliseconds, compressing a
        page with it a fraction of one. Not thread-safe, and the server only compresses on
        its event loop's thread.
        """
        return zstandard.ZstdCompressor(
            dict_data=self.zstd,
            write_checksum=False,
            write_content_size=True,
            write_dict_id=False,
        )

    @cached_property
    def decompressor(self) -> zstandard.ZstdDecompressor:
        """A decompressor bound to this dictionary."""
        return zstandard.ZstdDecompressor(dict_data=self.zstd)


def load_dictionary(path: Path | None = None) -> Dictionary:
    """The packaged dictionary, or the one at ``path``."""
    if path is None:
        data = resources.files("textwire.protocol").joinpath("data", DICTIONARY_FILE).read_bytes()
    else:
        data = path.read_bytes()
    return Dictionary(DICTIONARY_ID, data)


def compress(data: bytes, dictionary: Dictionary) -> bytes:
    """A zstd frame of ``data``: level 19, content size recorded, no checksum, no dict id."""
    return dictionary.compressor.compress(data)


def decompress(data: bytes, dictionary: Dictionary, max_size: int = MAX_TEXT_BYTES) -> bytes:
    """The bytes a zstd frame holds, refusing frames without a size or above ``max_size``."""
    try:
        parameters = zstandard.get_frame_parameters(data)
    except zstandard.ZstdError as error:
        msg = "not a zstd frame"
        raise CompressionError(msg) from error
    if parameters.content_size == zstandard.CONTENTSIZE_UNKNOWN:
        msg = "the frame does not declare its size"
        raise CompressionError(msg)
    if parameters.content_size > max_size:
        msg = f"the frame declares {parameters.content_size} bytes, more than {max_size}"
        raise CompressionError(msg)
    try:
        return dictionary.decompressor.decompress(data, allow_extra_data=False)
    except zstandard.ZstdError as error:
        msg = "the frame is corrupt or needs another dictionary"
        raise CompressionError(msg) from error
