"""The performance baseline: what a page costs in SMS, and how fast the server makes it.

``measure`` runs both halves over the recorded fixtures in ``protocol/fixtures``:

- **cost** is exact and repeatable. For every fixture document, at every alphabet and page
  size the vectors use: how many pages, how many SMS page 1 and the whole document take,
  and the text and payload bytes behind them; plus the plain-reply message counts. Fewer
  SMS is the only thing that saves money, so this is the number an optimisation must move.
- **speed** is timed: the median of several runs of each stage of the pipeline, and of a
  whole request through the real handler. It depends on the machine, which is recorded.

``compare`` reads two results and says, metric by metric, what got better or worse.
``textwire bench`` prints that comparison against ``benchmarks/baseline.json``;
``textwire bench --record`` replaces the baseline. A test keeps the committed baseline's
cost half equal to the code's, the way the vector check keeps the vectors honest.
"""

from __future__ import annotations

import asyncio
import json
import platform
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textwire import __version__
from textwire.clock import FakeClock
from textwire.config import Settings
from textwire.content.extract import extract_document
from textwire.content.fakes import load_fixtures
from textwire.content.pages import clear_page_cache, page_payload, paginate, plain_document_pages
from textwire.content.render import search_document
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.compress import compress, decompress, load_dictionary
from textwire.protocol.frames import body_bytes, decode_frame, encode_frame, split_payload
from textwire.service.store import Store
from textwire.service.wiring import build_components
from textwire.transport.fake import FakeTransport
from textwire.vectors.build import DOCUMENT_CUTS, FIXTURES

if TYPE_CHECKING:
    from collections.abc import Callable

    from textwire.content.document import Document
    from textwire.protocol.compress import Dictionary

BASELINE = Path("benchmarks") / "baseline.json"
#: A phone from Ofcom's drama range, so the benchmark can never text anyone.
PHONE = "+447700900123"
#: Plain-reply sizes measured, in messages a page.
PLAIN_SIZES = (4,)
#: How much slower a timing may be before it is reported, as a fraction of the baseline:
#: timings move with the machine and its load; SMS counts never do.
SPEED_TOLERANCE = 0.5


@dataclass(frozen=True)
class Change:
    """One metric that differs between two results."""

    metric: str
    before: float
    after: float
    worse: bool

    def describe(self) -> str:
        """``cost/notes/b64/12/sms_total: 9 -> 8 (better)``."""
        verdict = "worse" if self.worse else "better"
        return f"{self.metric}: {_number(self.before)} -> {_number(self.after)} ({verdict})"


def _number(value: float) -> str:
    return f"{value:g}"


def _documents(root: Path) -> dict[str, Document]:
    """The fixture documents, named as the document vectors name them."""
    fetcher, search = load_fixtures(root / FIXTURES)
    documents: dict[str, Document] = {}
    for url in sorted(fetcher.pages):
        name = url.split("://", 1)[1].split("/", 1)[0].replace(".", "-")
        documents[name] = extract_document(asyncio.run(fetcher.fetch(url)))
    for query in sorted(search.results):
        hits = asyncio.run(search.search(query, 5))
        documents["search-" + query.replace(" ", "-")] = search_document(query, hits)
    return documents


def _cost_of(document: Document, dictionary: Dictionary) -> dict[str, Any]:
    """Every SMS count and byte count of one document."""
    cuts: dict[str, Any] = {}
    for alphabet, size in DOCUMENT_CUTS:
        pages = paginate(document, dictionary, size, alphabet)
        payloads = [
            page_payload(document, dictionary, size, number, alphabet)
            for number in range(1, len(pages) + 1)
        ]
        frames = [len(split_payload(0, payload, alphabet)) for payload in payloads]
        text_bytes = sum(len(text.encode("utf-8")) for text in pages)
        payload_bytes = sum(len(payload) for payload in payloads)
        cuts[f"{alphabet.value}/{size}"] = {
            "pages": len(pages),
            "sms_first_page": frames[0],
            "sms_total": sum(frames),
            "text_bytes": text_bytes,
            "payload_bytes": payload_bytes,
            "ratio": round(text_bytes / payload_bytes, 3),
            # How full the SMS are: payload over what the frames could have carried.
            "fill": round(payload_bytes / (sum(frames) * body_bytes(alphabet)), 3),
        }
    for messages in PLAIN_SIZES:
        plain = plain_document_pages(document, messages)
        cuts[f"plain/{messages}"] = {
            "pages": len(plain),
            "sms_total": sum(len(page) for page in plain),
        }
    return cuts


def cost(root: Path) -> dict[str, Any]:
    """The cost half: exact, so any change to it is a change to what the server sends."""
    dictionary = load_dictionary()
    documents = {name: _cost_of(doc, dictionary) for name, doc in _documents(root).items()}
    totals: dict[str, int] = {}
    for cuts in documents.values():
        for cut, numbers in cuts.items():
            totals[cut] = totals.get(cut, 0) + numbers["sms_total"]
    return {
        "dictionary": {"sha256": dictionary.sha256, "bytes": len(dictionary.data)},
        "documents": documents,
        "sms_total": totals,
    }


def timed(
    run: Callable[[], object], repeats: int, clock: Callable[[], int] = time.perf_counter_ns
) -> float:
    """The median wall time of ``run`` over ``repeats`` calls, in milliseconds."""
    samples = []
    for _ in range(repeats):
        start = clock()
        run()
        samples.append((clock() - start) / 1e6)
    return round(statistics.median(samples), 4)


def speed(root: Path, repeats: int = 15) -> dict[str, float]:
    """The speed half: median milliseconds for each stage, over the fixtures."""
    dictionary = load_dictionary()
    fetcher, search = load_fixtures(root / FIXTURES)
    fetched = [asyncio.run(fetcher.fetch(url)) for url in sorted(fetcher.pages)]
    documents = list(_documents(root).values())
    article = max(documents, key=lambda document: len(document.body))
    text = article.body.encode("utf-8")
    packed = compress(text, dictionary)
    frames = split_payload(7, page_payload(article, dictionary, 12, 1), Alphabet.BASE64URL)
    encoded = [encode_frame(frame) for frame in frames]

    def paginate_all() -> None:
        clear_page_cache()
        for document in documents:
            paginate(document, dictionary, 12)

    transport = FakeTransport()
    components = build_components(
        Settings(  # type: ignore[call-arg]
            _env_file=None, allowed_numbers=(PHONE,), daily_segment_budget=10_000_000
        ),
        transport=transport,
        fetcher=fetcher,
        search=search,
        clock=FakeClock(),
        store=Store(":memory:"),
    )
    url = sorted(fetcher.pages)[0]
    query = sorted(search.results)[0]

    def request(text: str) -> None:
        asyncio.run(components.handler.handle(transport.deliver(PHONE, text)))

    results = {
        "extract_all_fixtures_ms": timed(
            lambda: [extract_document(page) for page in fetched], repeats
        ),
        "paginate_all_fixtures_ms": timed(paginate_all, repeats),
        "compress_article_ms": timed(lambda: compress(text, dictionary), repeats),
        "decompress_article_ms": timed(lambda: decompress(packed, dictionary), repeats),
        "encode_page_frames_ms": timed(lambda: [encode_frame(frame) for frame in frames], repeats),
        "decode_page_frames_ms": timed(lambda: [decode_frame(line) for line in encoded], repeats),
        "request_page_ms": timed(lambda: request(f"a7 g {url}"), repeats),
        "request_search_ms": timed(lambda: request(f"a8 s {query}"), repeats),
    }
    asyncio.run(components.aclose())
    return results


def measure(root: Path, repeats: int = 15) -> dict[str, Any]:
    """Both halves, with what they were measured on."""
    return {
        "version": __version__,
        "machine": {
            "python": platform.python_version(),
            "system": f"{platform.system()} {platform.release()}",
            "processor": platform.machine(),
        },
        "cost": cost(root),
        "speed": speed(root, repeats),
    }


def _flatten(value: Any, prefix: str = "") -> dict[str, float]:
    """``{"a": {"b": 1}}`` as ``{"a/b": 1}``, numbers only."""
    if isinstance(value, dict):
        flat: dict[str, float] = {}
        for key, item in value.items():
            flat.update(_flatten(item, f"{prefix}{key}/"))
        return flat
    if isinstance(value, bool) or not isinstance(value, int | float):
        return {}
    return {prefix.rstrip("/"): float(value)}


def _higher_is_better(metric: str) -> bool:
    return metric.endswith(("/ratio", "/fill"))


def compare(before: dict[str, Any], after: dict[str, Any]) -> list[Change]:
    """Every metric that moved: any cost change, and timings beyond the tolerance."""
    changes = []
    old_cost, new_cost = _flatten(before["cost"]), _flatten(after["cost"])
    for metric in sorted(old_cost.keys() | new_cost.keys()):
        old, new = old_cost.get(metric), new_cost.get(metric)
        if old is None or new is None or old == new:
            continue
        worse = new < old if _higher_is_better(metric) else new > old
        changes.append(Change(f"cost/{metric}", old, new, worse))
    old_speed, new_speed = _flatten(before["speed"]), _flatten(after["speed"])
    for metric in sorted(old_speed.keys() & new_speed.keys()):
        old, new = old_speed[metric], new_speed[metric]
        if abs(new - old) > old * SPEED_TOLERANCE:
            changes.append(Change(f"speed/{metric}", old, new, new > old))
    return changes


def load(path: Path) -> dict[str, Any]:
    """A recorded result."""
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def save(result: dict[str, Any], path: Path) -> None:
    """Write a result, stable and readable, so its diff is the review."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # LF on every platform, so recording on Windows does not rewrite every line of the file.
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
