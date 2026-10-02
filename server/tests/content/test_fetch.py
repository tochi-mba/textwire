from __future__ import annotations

import socket
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from textwire.content.fetch import (
    Fetched,
    FetchError,
    FetchFault,
    HttpxFetcher,
    SystemResolver,
    is_public_address,
)

PUBLIC = "93.184.215.14"


class StaticResolver:
    """Answers from a table; unknown hosts fail like a missing DNS name."""

    def __init__(self, table: dict[str, list[str]]) -> None:
        self.table = table
        self.asked: list[str] = []

    async def resolve(self, host: str) -> list[str]:
        self.asked.append(host)
        if host not in self.table:
            raise socket.gaierror(socket.EAI_NONAME, "unknown")
        return self.table[host]


def _fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
    table: dict[str, list[str]] | None = None,
    max_bytes: int = 1000,
    max_redirects: int = 5,
) -> HttpxFetcher:
    return HttpxFetcher(
        user_agent="textwire-test",
        timeout_seconds=5,
        max_bytes=max_bytes,
        max_redirects=max_redirects,
        resolver=StaticResolver(table if table is not None else {"site.example": [PUBLIC]}),
        transport=httpx.MockTransport(handler),
    )


async def test_a_page_is_fetched_with_our_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, text="<p>hi</p>"
        )

    async with _fetcher(handler) as fetcher:
        page = await fetcher.fetch("https://site.example/a")
    assert page == Fetched(
        url="https://site.example/a",
        final_url="https://site.example/a",
        status=200,
        content_type="text/html; charset=utf-8",
        body=b"<p>hi</p>",
    )
    assert page.media_type == "text/html"
    assert page.charset == "utf-8"
    assert seen[0].headers["user-agent"] == "textwire-test"


def test_a_page_without_a_charset_says_so() -> None:
    page = Fetched("u", "u", 200, "text/plain", b"")
    assert (page.media_type, page.charset) == ("text/plain", None)


async def test_redirects_are_followed_and_each_hop_is_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, text="new")

    resolver = StaticResolver({"site.example": [PUBLIC]})
    fetcher = HttpxFetcher(
        user_agent="t",
        timeout_seconds=5,
        max_bytes=100,
        resolver=resolver,
        transport=httpx.MockTransport(handler),
    )
    page = await fetcher.fetch("https://site.example/old")
    await fetcher.aclose()
    assert page.final_url == "https://site.example/new"
    assert resolver.asked == ["site.example", "site.example"]


async def test_a_redirect_into_the_private_network_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://router.local/admin"})

    fetcher = _fetcher(handler, {"site.example": [PUBLIC], "router.local": ["192.168.1.1"]})
    with pytest.raises(FetchError) as caught:
        await fetcher.fetch("https://site.example/")
    assert caught.value.fault is FetchFault.BLOCKED
    assert caught.value.status_text == "E fetch blocked"


async def test_more_than_five_redirects_fail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    with pytest.raises(FetchError) as caught:
        await _fetcher(handler).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.REDIRECTS


@pytest.mark.parametrize("status", [404, 500, 304])
async def test_errors_and_redirects_without_a_location_report_the_status(status: int) -> None:
    with pytest.raises(FetchError) as caught:
        await _fetcher(lambda _request: httpx.Response(status)).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.STATUS
    assert caught.value.status_text == f"E fetch status {status}"


async def test_a_declared_size_over_the_limit_is_refused_before_reading() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": "5000"}, content=b"x" * 5000)

    with pytest.raises(FetchError) as caught:
        await _fetcher(handler).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.TOO_LARGE


async def test_a_body_that_grows_past_the_limit_is_abandoned() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(20):
            yield b"x" * 100

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=chunks())

    with pytest.raises(FetchError) as caught:
        await _fetcher(handler).fetch("https://site.example/")
    assert caught.value.status_text == "E fetch too-large"


async def test_timeouts_are_reported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(FetchError) as caught:
        await _fetcher(handler).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.TIMEOUT


async def test_connection_failures_are_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(FetchError) as caught:
        await _fetcher(handler).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.NETWORK


async def test_unknown_hosts_are_network_errors() -> None:
    with pytest.raises(FetchError) as caught:
        await _fetcher(lambda _r: httpx.Response(200), {}).fetch("https://nowhere.example/")
    assert caught.value.fault is FetchFault.NETWORK


async def test_a_host_with_no_addresses_is_a_network_error() -> None:
    with pytest.raises(FetchError) as caught:
        await _fetcher(lambda _r: httpx.Response(200), {"site.example": []}).fetch(
            "https://site.example/"
        )
    assert caught.value.fault is FetchFault.NETWORK


@pytest.mark.parametrize(
    "url",
    [
        "ftp://site.example/",
        "file:///etc/passwd",
        "https:///nohost",
        "http://127.0.0.1/",
        "http://[::1]/",
    ],
)
async def test_other_schemes_missing_hosts_and_local_addresses_are_blocked(url: str) -> None:
    with pytest.raises(FetchError) as caught:
        await _fetcher(lambda _r: httpx.Response(200)).fetch(url)
    assert caught.value.fault is FetchFault.BLOCKED


async def test_a_public_ip_literal_needs_no_resolution() -> None:
    fetcher = _fetcher(lambda _r: httpx.Response(200, text="ok"), {})
    assert (await fetcher.fetch(f"http://{PUBLIC}/")).body == b"ok"


@pytest.mark.parametrize(
    ("address", "public"),
    [
        (PUBLIC, True),
        ("2606:4700:4700::1111", True),
        ("10.0.0.1", False),
        ("172.16.0.1", False),
        ("192.168.0.1", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),  # noqa: S104 - an address under test, not a bind
        ("224.0.0.251", False),
        ("::1", False),
        ("fe80::1%eth0", False),
        ("fd00::1", False),
        ("::ffff:10.0.0.1", False),
        ("::ffff:93.184.215.14", True),
        ("ff02::1", False),
    ],
)
def test_only_global_unicast_addresses_are_public(address: str, public: bool) -> None:
    assert is_public_address(address) is public


async def test_the_system_resolver_resolves_localhost() -> None:
    addresses = await SystemResolver().resolve("localhost")
    assert addresses
    assert not any(is_public_address(address) for address in addresses)


def _chain(redirects: int) -> tuple[Callable[[httpx.Request], httpx.Response], list[str]]:
    """A site that redirects ``redirects`` times before answering, and the paths it saw."""
    hops: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hops.append(request.url.path)
        if len(hops) <= redirects:
            return httpx.Response(302, headers={"location": f"/hop{len(hops)}"})
        return httpx.Response(200, text="arrived", headers={"content-type": "text/plain"})

    return handler, hops


@pytest.mark.parametrize("allowed", [0, 1, 3])
async def test_the_redirect_limit_is_a_setting(allowed: int) -> None:
    handler, hops = _chain(allowed)
    fetched = await _fetcher(handler, max_redirects=allowed).fetch("https://site.example/")
    assert fetched.body == b"arrived"
    assert len(hops) == allowed + 1
    handler, _ = _chain(allowed + 1)
    with pytest.raises(FetchError) as caught:
        await _fetcher(handler, max_redirects=allowed).fetch("https://site.example/")
    assert caught.value.fault is FetchFault.REDIRECTS
