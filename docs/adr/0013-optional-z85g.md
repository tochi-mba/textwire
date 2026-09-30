# ADR-0013: Optional Z85G frame encoding

**Status:** Accepted for software testing (2026-10-01); carrier acceptance pending.

## Decision

Retain base64url as the default and add the optional Z85G alphabet described in
`protocol/PROTOCOL.md`. Its leading full stop occupies the prefix reserved by ADR-0003.
This supersedes ADR-0003's decision to defer implementation of a denser alphabet.

The six-byte header remains identical. Each SMS can carry 121 payload bytes instead of
114, a 6.1% capacity increase. Actual segment savings depend on payload length.
The alphabet contains 85 distinct printable ASCII characters in the GSM-7 basic table;
the earlier ADR's count of 83 was incorrect.

## Validation

Property tests check canonical round trips and single-septet characters. Golden vectors
cover both alphabets, malformed encodings and the largest frame for each alphabet.
No carrier preservation or delivery result has been observed. Keep the default until
the route's alphabet probe passes; record hardware evidence in `docs/ACCEPTANCE.md`.
