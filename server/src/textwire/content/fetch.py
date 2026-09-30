"""Fetching pages without becoming a way into the owner's network (SECURITY.md).

Every hop of a fetch is checked the same way: the scheme is http or https, and every address
the host resolves to is globally routable. Redirects are followed by hand so each hop is
checked, and a body is abandoned as soon as it passes the size limit.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from email.message import Message
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

if TYPE_CHECKING:
    from types import TracebackType

MAX_REDIRECTS = 5


class FetchFault(StrEnum):
    """Why a fetch failed; the value is what the phone sees after ``E fetch``."""

    TIMEOUT = "timeout"
    STATUS = "status"
    TOO_LARGE = "too-large"
    BLOCKED = "blocked"
    REDIRECTS = "redirects"
    NETWORK = "network"


class FetchError(Exception):
    """A page could not be fetched."""

    def __init__(self, fault: FetchFault, detail: str = "") -> None:
        super().__init__(f"{fault.value} {detail}".strip())
        self.fault = fault
        self.detail = detail

    @property
    def status_text(self) -> str:
        """The status line the phone is sent: ``E fetch status 404``."""
        return f"E fetch {self}"


@dataclass(frozen=True, slots=True)
class Fetched:
    """A fetched response body and what is known about it."""

    url: str
    final_url: str
    status: int
    content_type: str
    body: bytes

    @property
    def media_type(self) -> str:
        """The content type without parameters, lower case: ``text/html``."""
        return self.content_type.split(";", 1)[0].strip().lower()

    @property
    def charset(self) -> str | None:
        """The charset parameter of the content type, if any."""
        message = Message()
        message["content-type"] = self.content_type
        charset = message.get_param("charset")
        return charset if isinstance(charset, str) else None


class Fetcher(Protocol):
    """Anything that can fetch a URL."""

    async def fetch(self, url: str) -> Fetched:
        """The response for ``url``, or :class:`FetchError`."""
        ...

    async def aclose(self) -> None:
        """Release connections."""
        ...


class Resolver(Protocol):
    """Name resolution, behind an interface so tests never touch DNS."""

    async def resolve(self, host: str) -> list[str]:
        """Every address ``host`` resolves to."""
        ...


class SystemResolver:
    """The operating system's resolver."""

    async def resolve(self, host: str) -> list[str]:
        """Every address ``host`` resolves to, sorted."""
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return sorted({str(info[4][0]) for info in infos})


def is_public_address(address: str) -> bool:
    """Whether an address is globally routable: not private, local, reserved or multicast."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


class HttpxFetcher:
    """Fetches with httpx, checking every hop and capping every body."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float,
        max_bytes: int,
        resolver: Resolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_bytes = max_bytes
        self._resolver = resolver if resolver is not None else SystemResolver()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
                "Accept-Language": "en-GB,en;q=0.8",
            },
        )

    async def __aenter__(self) -> HttpxFetcher:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._client.aclose()

    async def _check(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError(FetchFault.BLOCKED)
        host = parts.hostname
        if _is_ip_literal(host):
            addresses = [host]
        else:
            try:
                addresses = await self._resolver.resolve(host)
            except OSError as error:
                raise FetchError(FetchFault.NETWORK) from error
        if not addresses:
            raise FetchError(FetchFault.NETWORK)
        if not all(is_public_address(address) for address in addresses):
            raise FetchError(FetchFault.BLOCKED)

    async def _read(self, response: httpx.Response) -> bytes:
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self._max_bytes:
            raise FetchError(FetchFault.TOO_LARGE)
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise FetchError(FetchFault.TOO_LARGE)
            chunks.append(chunk)
        return b"".join(chunks)

    async def fetch(self, url: str) -> Fetched:
        """The response for ``url`` after at most five checked redirects."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await self._check(current)
            try:
                async with self._client.stream("GET", current) as response:
                    location = response.headers.get("location")
                    if response.is_redirect and location:
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 300:  # noqa: PLR2004
                        raise FetchError(FetchFault.STATUS, str(response.status_code))
                    body = await self._read(response)
                    return Fetched(
                        url=url,
                        final_url=current,
                        status=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        body=body,
                    )
            except httpx.TimeoutException as error:
                raise FetchError(FetchFault.TIMEOUT) from error
            except httpx.HTTPError as error:
                raise FetchError(FetchFault.NETWORK) from error
        raise FetchError(FetchFault.REDIRECTS)
