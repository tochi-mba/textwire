# Architecture decision records

Each record captures one decision that someone could reasonably have made differently: the
context, the decision, why, what it costs, and what evidence would change it. Records are
append-only once accepted. A changed decision gets a new record that supersedes the old
one, and the old one's status says so.

To add one, copy the shape of an existing record, take the next number, and add a row
here. A test fails if a record is missing from this table or a number is skipped.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-monorepo-protocol-server-android.md) | One repository with `protocol/`, `server/` and `android/` | Accepted |
| [0002](0002-a-frame-is-one-single-segment-sms.md) | A frame is one single-segment SMS, reassembled by us | Accepted |
| [0003](0003-base64url-frames.md) | Frames are base64url; denser alphabets are reserved, not built | Accepted |
| [0004](0004-zstd-with-a-trained-dictionary.md) | zstd with a trained dictionary; Brotli rejected | Accepted |
| [0005](0005-twilio-inbound-by-polling.md) | Twilio inbound by polling; no public endpoint needed | Accepted |
| [0006](0006-standalone-repo-with-family-conventions.md) | A standalone repository that copies the LUCY family conventions | Accepted |
| [0007](0007-requests-are-plain-text.md) | Requests are plain text, and `!` answers in plain text | Accepted |
| [0008](0008-numbered-link-chips.md) | Links become numbered chips; the server keeps the URLs | Accepted |
| [0009](0009-coverage-floors.md) | 100% coverage on the server and on all Kotlin logic; screens held by line | Accepted |
| [0010](0010-carrier-terms-and-person-like-traffic.md) | The phone only ever sends what a person would | Accepted |
| [0011](0011-not-the-default-sms-app-in-v1.md) | Not the default SMS app in v1; minSdk 31 | Accepted |
| [0012](0012-daily-segment-budget.md) | A hard daily segment budget with a cost meter | Accepted |
| [0013](0013-optional-z85g.md) | Optional Z85G encoding; base64url remains the default | Accepted for software testing |
