"""Twilio: a small client over its REST API, and the transport built on it (ADR-0005).

Two endpoints do all the work: ``POST Messages.json`` sends one SMS, and ``GET Messages.json``
lists messages to the server's number, which is how inbound requests are found without a
webhook. ``GET Messages/{sid}.json`` fetches a sent message's delivery status and price. The
client is hand-written on httpx because it is eighty lines and then every byte of it is
under test.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

import httpx

from textwire.transport.base import DeliveryStatus, InboundMessage, SentMessage, TransportError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from textwire.clock import Clock
    from textwire.service.store import Store

log = logging.getLogger(__name__)

API_VERSION = "2010-04-01"
PAGE_SIZE = 100
#: The most pages one listing follows: 5,000 messages, far more than an hour's lookback holds.
MAX_LIST_PAGES = 50
#: HTTP statuses after which the same request may succeed.
RETRYABLE = frozenset({408, 429, 500, 502, 503, 504})
#: Poll this far behind the newest message seen, so a message Twilio records late is not missed.
OVERLAP = timedelta(minutes=10)
LAST_SEEN_KEY = "twilio_last_seen"


@dataclass(frozen=True, slots=True)
class MessageResource:
    """The fields of a Twilio Message resource the server reads."""

    sid: str
    direction: str
    status: str
    sender: str
    recipient: str
    body: str
    date_sent: datetime | None
    date_created: datetime
    price: float | None
    price_unit: str | None
    error_code: int | None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> MessageResource:
        """A resource from Twilio's JSON representation."""
        return cls(
            sid=str(data["sid"]),
            direction=str(data.get("direction") or ""),
            status=str(data.get("status") or ""),
            sender=str(data.get("from") or ""),
            recipient=str(data.get("to") or ""),
            body=str(data.get("body") or ""),
            date_sent=_rfc2822(data.get("date_sent")),
            date_created=_rfc2822(data.get("date_created")) or datetime.now(UTC),
            price=float(data["price"]) if data.get("price") is not None else None,
            price_unit=str(data["price_unit"]) if data.get("price_unit") else None,
            error_code=int(data["error_code"]) if data.get("error_code") is not None else None,
        )


def _rfc2822(value: object) -> datetime | None:
    if not value:
        return None
    return parsedate_to_datetime(str(value)).astimezone(UTC)


def _twilio_error(response: httpx.Response) -> TransportError:
    try:
        payload = response.json()
        message = str(payload.get("message") or response.text)
        code = payload.get("code")
    except ValueError:
        message, code = response.text, None
    return TransportError(
        f"twilio {response.status_code}: {message}",
        retryable=response.status_code in RETRYABLE,
        code=int(code) if isinstance(code, int) else None,
    )


class TwilioClient:
    """The three REST calls the server makes."""

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        base_url: str = "https://api.twilio.com",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._sid = account_sid
        self._root = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=f"{self._root}/{API_VERSION}/Accounts/{account_sid}",
            auth=(account_sid, auth_token),
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as error:
            message = "twilio: timed out"
            raise TransportError(message, retryable=True) from error
        except httpx.HTTPError as error:
            message = f"twilio: {error}"
            raise TransportError(message, retryable=True) from error
        if response.status_code >= 400:  # noqa: PLR2004 - HTTP's own boundary
            raise _twilio_error(response)
        return response.json()

    async def send(self, *, sender: str, recipient: str, body: str) -> MessageResource:
        """Send one SMS from ``sender`` to ``recipient``."""
        data = await self._request(
            "POST", "/Messages.json", data={"From": sender, "To": recipient, "Body": body}
        )
        return MessageResource.from_json(data)

    async def get(self, sid: str) -> MessageResource:
        """One message's current state."""
        return MessageResource.from_json(await self._request("GET", f"/Messages/{sid}.json"))

    async def list_to(self, recipient: str, since: datetime) -> list[MessageResource]:
        """Every message sent to ``recipient`` since ``since``, following the pages."""
        params: dict[str, str] = {
            "To": recipient,
            "DateSent>": since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "PageSize": str(PAGE_SIZE),
        }
        messages: list[MessageResource] = []
        data = await self._request("GET", "/Messages.json", params=params)
        pages = 1
        while True:
            messages.extend(MessageResource.from_json(item) for item in data.get("messages", []))
            next_page = data.get("next_page_uri")
            if not next_page:
                return messages
            if pages == MAX_LIST_PAGES:
                log.warning("stopped following message pages", extra={"pages": pages})
                return messages
            # next_page_uri is an absolute path; joined to the host it overrides the base URL.
            data = await self._request("GET", f"{self._root}{next_page}")
            pages += 1


class TwilioTransport:
    """The :class:`~textwire.transport.base.Transport` over Twilio, receiving by polling."""

    def __init__(
        self,
        *,
        client: TwilioClient,
        number: str,
        store: Store,
        clock: Clock,
        poll_seconds: float,
        lookback: timedelta,
    ) -> None:
        self._client = client
        self._number = number
        self._store = store
        self._clock = clock
        self._poll = poll_seconds
        self._lookback = lookback

    @property
    def number(self) -> str:
        """The server's number."""
        return self._number

    def _since(self) -> datetime:
        last = self._store.get_state(LAST_SEEN_KEY)
        if last is None:
            return self._clock.now() - self._lookback
        return datetime.fromisoformat(last) - OVERLAP

    async def poll(self) -> list[InboundMessage]:
        """One poll: the inbound messages Twilio lists that the store has not seen."""
        found = await self._client.list_to(self._number, self._since())
        newest: datetime | None = None
        messages: list[InboundMessage] = []
        for resource in sorted(found, key=lambda item: (item.date_created, item.sid)):
            if resource.direction != "inbound":
                continue
            newest = max(newest or resource.date_created, resource.date_created)
            if self._store.seen_inbound(resource.sid):
                continue
            messages.append(
                InboundMessage(
                    id=resource.sid,
                    sender=resource.sender,
                    recipient=resource.recipient,
                    text=resource.body,
                    received_at=resource.date_created,
                )
            )
        if newest is not None:
            self._store.set_state(LAST_SEEN_KEY, newest.isoformat())
        return messages

    async def receive(self) -> AsyncGenerator[InboundMessage]:
        """Inbound messages as they arrive, polling forever; provider errors are logged."""
        while True:
            try:
                for message in await self.poll():
                    yield message
            except TransportError as error:
                log.warning("poll failed", extra={"error": str(error)})
            await self._clock.sleep(self._poll)

    async def send(self, recipient: str, text: str) -> SentMessage:
        """Hand one SMS to Twilio."""
        resource = await self._client.send(sender=self._number, recipient=recipient, body=text)
        return SentMessage(id=resource.sid, recipient=recipient, text=text)

    async def status(self, message_id: str) -> DeliveryStatus | None:
        """What Twilio knows about a sent message."""
        resource = await self._client.get(message_id)
        return DeliveryStatus(
            id=resource.sid,
            status=resource.status,
            price=abs(resource.price) if resource.price is not None else None,
            price_unit=resource.price_unit,
            error_code=resource.error_code,
        )

    async def aclose(self) -> None:
        """Close the client."""
        await self._client.aclose()


def webhook_signature(url: str, form: Mapping[str, str], auth_token: str) -> str:
    """The ``X-Twilio-Signature`` Twilio sends for ``url`` and a form body."""
    payload = url + "".join(key + form[key] for key in sorted(form))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def signature_matches(url: str, form: Mapping[str, str], auth_token: str, given: str) -> bool:
    """Whether ``given`` is the signature Twilio would have sent."""
    return hmac.compare_digest(webhook_signature(url, form, auth_token), given)
