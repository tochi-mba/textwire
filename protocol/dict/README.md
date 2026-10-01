# The shared zstd dictionary

`textwire-v1.zdict` is codec 1 (PROTOCOL.md section 4). It was trained by
`server/scripts/train_dictionary.py` on pages and search results fetched for the queries
in `corpus-queries.txt`; the pages it used are listed in `corpus-urls.txt`. The server
package carries a byte-for-byte copy, and a test keeps the two identical.

Trained 2026-10-01 on 1233 page-sized samples; 309 more were held out and never seen in training. The table measures the held-out
samples at level 19, the production setting.

| Dictionary size | SHA-256 | Without dictionary | With dictionary | Held-out bytes |
| --- | --- | --- | --- | --- |
| 110 KiB | `51edaa2a0ade50e9...` | 2.18x | 2.88x | 941,005 to 327,202 |
| 220 KiB | `5ef1ea8648b43106...` | 2.18x | 2.98x | 941,005 to 315,531 |
| 440 KiB | `ebd335345b91067c...` | 2.18x | 3.10x | 941,005 to 304,007 |
| 880 KiB (chosen) | `0bd405e0b822b1e1...` | 2.18x | 3.25x | 941,005 to 289,748 |

Chosen dictionary SHA-256: `0bd405e0b822b1e1ad6d91f365e8ff856875baa7683a91108beefdaea5b29046`

Replacing this file changes every compressed golden vector. After v1 ships, a retrained
dictionary is a new file with a new codec number, never an edit of this one.
