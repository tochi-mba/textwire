# The shared zstd dictionary

`textwire-v1.zdict` is codec 1 (PROTOCOL.md section 4). It was trained by
`server/scripts/train_dictionary.py` on pages and search results fetched for the queries
in `corpus-queries.txt`; the pages it used are listed in `corpus-urls.txt`. The server
package carries a byte-for-byte copy, and a test keeps the two identical.

Trained 2026-09-30 on 1233 page-sized samples; 309 more were held out and never seen in training. The table measures the held-out
samples at level 19, the production setting.

| Dictionary size | SHA-256 | Without dictionary | With dictionary | Held-out bytes |
| --- | --- | --- | --- | --- |
| 32 KiB | `57e4f15fae022791...` | 2.18x | 2.72x | 933,549 to 343,053 |
| 64 KiB | `1794ff1bbc376ac8...` | 2.18x | 2.82x | 933,549 to 331,194 |
| 110 KiB (chosen) | `9abf43a638bf856f...` | 2.18x | 2.86x | 933,549 to 326,860 |

Chosen dictionary SHA-256: `9abf43a638bf856f587437d50c990ec4687780af90447b6592f98f46f7b7a9a2`

Replacing this file changes every compressed golden vector. After v1 ships, a retrained
dictionary is a new file with a new codec number, never an edit of this one.
