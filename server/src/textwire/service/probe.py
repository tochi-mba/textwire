"""The route probe: one frame holding every byte value (docs/OPERATIONS.md section 5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textwire.protocol.frames import Frame, body_bytes, encode_frame
from textwire.protocol.tags import TAG_COUNT

if TYPE_CHECKING:
    from textwire.config import Settings

#: The tag a probe frame carries: the last server tag, which a phone never allocates.
PROBE_TAG = TAG_COUNT - 1


def probe_frame(settings: Settings) -> str:
    """A frame whose body cycles through every byte value the alphabet must carry."""
    size = body_bytes(settings.frame_alphabet)
    body = bytes((index * 7 + 3) % 256 for index in range(size))
    return encode_frame(Frame(tag=PROBE_TAG, seq=0, total=1, body=body), settings.frame_alphabet)
