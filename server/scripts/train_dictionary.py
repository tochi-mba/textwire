#!/usr/bin/env python3
"""Train ``protocol/dict/textwire-v1.zdict`` from a corpus fetched from the real web.

Usage (from ``server/``)::

    uv run python scripts/train_dictionary.py              # fetch, train, measure, report
    uv run python scripts/train_dictionary.py --write      # ...and replace the dictionary
    uv run python scripts/train_dictionary.py --from-cache # reuse protocol/dict/cache/

1. Every query in ``protocol/dict/corpus-queries.txt`` is searched, and its results page is
   rendered exactly as the server renders one.
2. The top pages of every search are fetched (cached in ``protocol/dict/cache/``, which is
   gitignored) and extracted exactly as the server extracts them.
3. Every document is cut into page-sized samples; every fifth sample is held out.
4. A dictionary is trained at each size and measured on the held-out samples.
5. With ``--write``, the best dictionary replaces ``protocol/dict/textwire-v1.zdict`` and the
   server package's copy, and ``protocol/dict/README.md`` records the run.

Replacing the dictionary changes every compressed golden vector: run ``make vectors``
afterwards. Replacing it after the protocol has shipped is a protocol change (a new file and
codec id), not an edit; see docs/adr/0004-zstd-with-a-trained-dictionary.md.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from textwire.config import DEFAULT_USER_AGENT
from textwire.content.extract import ExtractError, extract_document
from textwire.content.fetch import Fetched, FetchError, HttpxFetcher
from textwire.content.pages import title_line
from textwire.content.render import search_document
from textwire.content.search import DdgsSearchProvider, Hit, SearchError
from textwire.protocol.compress import DICTIONARY_FILE
from textwire.protocol.training import (
    measure,
    samples_from_text,
    split_held_out,
    train,
)

SERVER = Path(__file__).resolve().parents[1]
DICT_DIR = SERVER.parent / "protocol" / "dict"
CACHE = DICT_DIR / "cache"
PACKAGE_COPY = SERVER / "src" / "textwire" / "protocol" / "data" / DICTIONARY_FILE
PAGES_PER_QUERY = 8
SIZES = (110 * 1024, 220 * 1024, 440 * 1024, 880 * 1024)


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def _queries() -> list[str]:
    lines = (DICT_DIR / "corpus-queries.txt").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


async def _search(provider: DdgsSearchProvider, query: str, from_cache: bool) -> list[Hit]:
    path = CACHE / f"search-{_key(query)}.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    elif from_cache:
        return []
    else:
        try:
            hits = await provider.search(query, PAGES_PER_QUERY)
        except SearchError as error:
            print(f"  search failed: {query!r}: {error}")
            return []
        rows = [{"title": hit.title, "url": hit.url, "snippet": hit.snippet} for hit in hits]
        if rows:  # an empty answer is often a rate limit; try again next run
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        await asyncio.sleep(2.0)  # be polite to the search engines
    return [Hit(row["title"], row["url"], row["snippet"]) for row in rows]


async def _fetch(fetcher: HttpxFetcher, url: str, from_cache: bool) -> Fetched | None:
    meta, body = CACHE / f"page-{_key(url)}.json", CACHE / f"page-{_key(url)}.bin"
    if meta.exists():
        info = json.loads(meta.read_text(encoding="utf-8"))
        return Fetched(url, info["final_url"], 200, info["content_type"], body.read_bytes())
    if from_cache:
        return None
    try:
        fetched = await fetcher.fetch(url)
    except FetchError as error:
        print(f"  fetch failed: {url}: {error}")
        return None
    body.write_bytes(fetched.body)
    meta.write_text(
        json.dumps({"final_url": fetched.final_url, "content_type": fetched.content_type}),
        encoding="utf-8",
    )
    return fetched


async def _corpus(from_cache: bool) -> tuple[list[bytes], list[str]]:
    CACHE.mkdir(parents=True, exist_ok=True)
    provider = DdgsSearchProvider(region="uk-en", backend="auto", timeout_seconds=30)
    samples: list[bytes] = []
    urls: list[str] = []
    async with HttpxFetcher(
        user_agent=DEFAULT_USER_AGENT, timeout_seconds=20, max_bytes=3_000_000
    ) as fetcher:
        gate = asyncio.Semaphore(8)

        async def one(url: str) -> None:
            async with gate:
                fetched = await _fetch(fetcher, url, from_cache)
            if fetched is None:
                return
            try:
                document = extract_document(fetched)
            except ExtractError:
                return
            urls.append(url)
            text = f"{title_line(document.title, 160)}\n\n{document.body}"
            samples.extend(samples_from_text(text))

        for query in _queries():
            hits = await _search(provider, query, from_cache)
            print(f"{query!r}: {len(hits)} results")
            document = search_document(query, hits)
            samples.extend(
                samples_from_text(f"{title_line(document.title, 160)}\n\n{document.body}")
            )
            await asyncio.gather(*(one(hit.url) for hit in hits))
    return samples, sorted(urls)


def _report(
    rows: list[tuple[int, str, float, float, int, int]], chosen: int, count: int, held: int
) -> str:
    lines = [
        "# The shared zstd dictionary",
        "",
        "`textwire-v1.zdict` is codec 1 (PROTOCOL.md section 4). It was trained by",
        "`server/scripts/train_dictionary.py` on pages and search results fetched for the queries",
        "in `corpus-queries.txt`; the pages it used are listed in `corpus-urls.txt`. The server",
        "package carries a byte-for-byte copy, and a test keeps the two identical.",
        "",
        f"Trained {datetime.now(UTC).date().isoformat()} on {count} page-sized samples; "
        f"{held} more were held out and never seen in training. The table measures the held-out",
        "samples at level 19, the production setting.",
        "",
        "| Dictionary size | SHA-256 | Without dictionary | With dictionary | Held-out bytes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for size, sha, plain_ratio, dict_ratio, raw, compressed in rows:
        mark = " (chosen)" if size == chosen else ""
        lines.append(
            f"| {size // 1024} KiB{mark} | `{sha[:16]}...` | {plain_ratio:.2f}x | "
            f"{dict_ratio:.2f}x | {raw:,} to {compressed:,} |"
        )
    chosen_sha = next(row[1] for row in rows if row[0] == chosen)
    lines += [
        "",
        f"Chosen dictionary SHA-256: `{chosen_sha}`",
        "",
        "Replacing this file changes every compressed golden vector. After v1 ships, a retrained",
        "dictionary is a new file with a new codec number, never an edit of this one.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Build the corpus, train at each size, report, and optionally write the best."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--from-cache", action="store_true", help="use only cached downloads")
    parser.add_argument("--write", action="store_true", help="replace the dictionary files")
    args = parser.parse_args()

    samples, urls = asyncio.run(_corpus(args.from_cache))
    training, held_out = split_held_out(samples)
    print(f"{len(samples)} samples: {len(training)} to train, {len(held_out)} held out")
    rows: list[tuple[int, str, float, float, int, int]] = []
    dictionaries: dict[int, bytes] = {}
    for size in SIZES:
        dictionary = train(training, size)
        dictionaries[size] = dictionary
        result = measure(dictionary, held_out)
        sha = hashlib.sha256(dictionary).hexdigest()
        rows.append(
            (
                size,
                sha,
                result.plain_ratio,
                result.dictionary_ratio,
                result.raw_bytes,
                result.dictionary_bytes,
            )
        )
        print(
            f"{size // 1024:>4} KiB: {result.plain_ratio:.2f}x without, "
            f"{result.dictionary_ratio:.2f}x with ({result.dictionary_bytes:,} bytes)"
        )
    chosen = min(rows, key=lambda row: row[5])[0]
    print(f"best: {chosen // 1024} KiB")
    if args.write:
        for path in (DICT_DIR / DICTIONARY_FILE, PACKAGE_COPY):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(dictionaries[chosen])
        (DICT_DIR / "README.md").write_text(
            _report(rows, chosen, len(training), len(held_out)), encoding="utf-8"
        )
        (DICT_DIR / "corpus-urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
        print("written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
