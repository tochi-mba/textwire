"""The golden vectors: every byte-level rule of PROTOCOL.md as committed JSON cases.

``build`` produces every file from fixed inputs, the committed dictionary and the recorded
fixtures; ``write`` puts them in ``protocol/vectors/``; ``check`` reports any difference in
either direction. The Kotlin suite reads the same files.
"""

from textwire.vectors.build import build, check, find_repo_root, write

__all__ = ["build", "check", "find_repo_root", "write"]
