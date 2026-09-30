"""Writing and checking the vector files, and the cases that need the content pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textwire.content.extract import extract_document
from textwire.content.fakes import load_fixtures
from textwire.content.pages import page_payload, paginate, plain_document_pages
from textwire.content.render import search_document
from textwire.protocol.alphabets import Alphabet
from textwire.protocol.compress import load_dictionary
from textwire.protocol.plain import format_plain_page
from textwire.vectors.cases import envelope_cases, frame_cases, ids, request_cases

if TYPE_CHECKING:
    from collections.abc import Iterator

    from textwire.content.document import Document
    from textwire.protocol.compress import Dictionary

MARKER = Path("protocol") / "PROTOCOL.md"
VECTORS = Path("protocol") / "vectors"
FIXTURES = Path("protocol") / "fixtures"
MANIFEST = "manifest.json"
#: Every document vector is cut at the default size and a small one in the default alphabet,
#: and at the default size in the dense one.
DOCUMENT_CUTS = ((Alphabet.BASE64URL, 12), (Alphabet.BASE64URL, 4), (Alphabet.Z85G, 12))
PLAIN_SIZES = (4, 2)


def find_repo_root(start: Path | None = None) -> Path:
    """The textwire checkout containing ``start`` (the working directory by default)."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / MARKER).is_file():
            return folder
    msg = f"{here} is not inside a textwire checkout (no {MARKER.as_posix()} above it)"
    raise FileNotFoundError(msg)


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _documents(root: Path) -> Iterator[tuple[str, Document]]:
    fetcher, search = load_fixtures(root / FIXTURES)
    for url in sorted(fetcher.pages):
        name = url.split("://", 1)[1].split("/", 1)[0].replace(".", "-")
        yield name, extract_document(asyncio.run(fetcher.fetch(url)))
    for query in sorted(search.results):
        hits = asyncio.run(search.search(query, 5))
        yield "search-" + query.replace(" ", "-"), search_document(query, hits)


def _document_case(document: Document, dictionary: Dictionary) -> dict[str, Any]:
    sizes: dict[str, list[dict[str, Any]]] = {}
    for alphabet, size in DOCUMENT_CUTS:
        pages = paginate(document, dictionary, size, alphabet)
        sizes[f"{alphabet.value}/{size}"] = [
            {
                "text": text,
                "payload_hex": page_payload(document, dictionary, size, number, alphabet).hex(),
            }
            for number, text in enumerate(pages, 1)
        ]
    return {
        "kind": int(document.kind),
        "title": document.title,
        "body": document.body,
        "links": list(document.links),
        "source": document.source,
        "pages": sizes,
    }


def _plain_case(document: Document) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for messages in PLAIN_SIZES:
        pages = plain_document_pages(document, messages)
        result[str(messages)] = [
            format_plain_page(bodies, "a7", number + 1 if number < len(pages) else None)
            for number, bodies in enumerate(pages, 1)
        ]
    return result


def build(root: Path) -> dict[str, str]:
    """Every vector file's path (relative to ``protocol/vectors``) and exact contents."""
    dictionary = load_dictionary()
    files: dict[str, str] = {}
    cases = [*frame_cases(), *request_cases(), *envelope_cases(dictionary)]
    for name, case in cases:
        files[f"{name}.json"] = _dump(case)
    for name, document in _documents(root):
        files[f"documents/{name}.json"] = _dump(_document_case(document, dictionary))
        files[f"plain/{name}.json"] = _dump(_plain_case(document))
    files["ids.json"] = _dump(ids(dictionary))
    manifest = {
        path: hashlib.sha256(text.encode("utf-8")).hexdigest() for path, text in files.items()
    }
    files[MANIFEST] = _dump({"files": dict(sorted(manifest.items()))})
    return files


def _on_disk(folder: Path) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8")
        for path in folder.rglob("*.json")
    }


def check(root: Path) -> list[str]:
    """Every difference between the committed vectors and what the reference produces."""
    expected, actual = build(root), _on_disk(root / VECTORS)
    problems = [f"missing: {path}" for path in sorted(expected.keys() - actual.keys())]
    problems += [f"unexpected: {path}" for path in sorted(actual.keys() - expected.keys())]
    problems += [
        f"changed: {path}"
        for path in sorted(expected.keys() & actual.keys())
        if expected[path] != actual[path]
    ]
    return problems


def write(root: Path) -> list[str]:
    """Rewrite ``protocol/vectors`` from the reference; return what changed."""
    folder = root / VECTORS
    changes = check(root)
    for path in folder.rglob("*.json"):
        path.unlink()
    for relative, text in build(root).items():
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return changes
