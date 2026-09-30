"""The wire format: the reference implementation of ``protocol/PROTOCOL.md``.

Pure functions and small value types only. Nothing here does I/O, reads the clock or knows
about SMS providers, so every rule can be tested exhaustively and turned into golden vectors
for the Kotlin implementation.
"""
