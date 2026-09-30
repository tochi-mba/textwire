from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tests.conftest import OTHER_PHONE, PHONE
from tests.service.conftest import memory_store
from textwire.clock import EPOCH
from textwire.content.document import Document
from textwire.protocol.envelope import Kind
from textwire.service.store import SCHEMA_VERSION, Store
from textwire.transport.base import DeliveryStatus, InboundMessage, SentMessage

DOC = Document(kind=Kind.PAGE, title="T", body="B[1]", links=("https://x.example",), source="s")


def _store() -> Store:
    return memory_store()


def test_a_new_database_has_the_current_schema() -> None:
    store = _store()
    assert store.schema_version == SCHEMA_VERSION
    assert store.ping()


def test_a_file_database_reopens_with_its_data(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    first = Store(path)
    first.set_state("k", "v")
    first.close()
    second = Store(path)
    assert second.get_state("k") == "v"
    assert second.schema_version == SCHEMA_VERSION
    second.close()


def test_inbound_messages_are_recorded_once_and_marked_handled() -> None:
    store = _store()
    message = InboundMessage("IN1", PHONE, "+447700900000", "a7 ?", EPOCH)
    assert not store.seen_inbound("IN1")
    store.record_inbound(message)
    store.record_inbound(message)
    assert store.seen_inbound("IN1")
    assert store.unhandled() == ["IN1"]
    store.mark_handled("IN1", EPOCH)
    assert store.unhandled() == []


def test_documents_are_found_through_any_response_that_used_them() -> None:
    store = _store()
    document_id = store.save_document(PHONE, DOC, page_size=12, plain=False, at=EPOCH)
    store.link_response(PHONE, 1, document_id, EPOCH)
    store.link_response(PHONE, 2, document_id, EPOCH)
    for tag in (1, 2):
        stored = store.document_for(PHONE, tag)
        assert stored is not None
        assert (stored.id, stored.document, stored.page_size, stored.plain) == (
            document_id,
            DOC,
            12,
            False,
        )


def test_responses_are_kept_apart_by_number() -> None:
    store = _store()
    document_id = store.save_document(PHONE, DOC, page_size=4, plain=True, at=EPOCH)
    store.link_response(PHONE, 1, document_id, EPOCH)
    assert store.document_for(OTHER_PHONE, 1) is None


def test_a_status_response_has_no_document() -> None:
    store = _store()
    store.link_response(PHONE, 3, None, EPOCH)
    assert store.document_for(PHONE, 3) is None


def test_frames_are_stored_and_a_reused_tag_forgets_them() -> None:
    store = _store()
    store.link_response(PHONE, 5, None, EPOCH)
    store.save_frames(PHONE, 5, {0: "AAA", 1: "BBB", 2: "CCC"}, EPOCH)
    assert store.load_frames(PHONE, 5, [2, 0, 9]) == {0: "AAA", 2: "CCC"}
    assert store.load_frames(OTHER_PHONE, 5, [0]) == {}
    store.link_response(PHONE, 5, None, EPOCH)
    assert store.load_frames(PHONE, 5, [0, 1, 2]) == {}


def test_outbound_messages_are_followed_until_final() -> None:
    store = _store()
    store.record_outbound(SentMessage("SM1", PHONE, "x"), tag=1, seq=0, at=EPOCH)
    store.record_outbound(SentMessage("SM2", PHONE, "y"), tag=None, seq=None, at=EPOCH)
    pending = store.pending_outbound(since=EPOCH - timedelta(hours=1))
    assert [(row.id, row.status, row.retried) for row in pending] == [
        ("SM1", "queued", False),
        ("SM2", "queued", False),
    ]
    store.update_outbound(DeliveryStatus("SM1", "sent"))
    store.update_outbound(DeliveryStatus("SM1", "delivered", 0.056, "USD"))
    store.update_outbound(DeliveryStatus("SM2", "failed"))
    assert store.pending_outbound(since=EPOCH - timedelta(hours=1)) == []
    assert store.actual_cost(EPOCH.date()) == (0.056, "USD")


def test_old_outbound_messages_are_not_followed() -> None:
    store = _store()
    store.record_outbound(SentMessage("SM1", PHONE, "x"), tag=1, seq=0, at=EPOCH)
    assert store.pending_outbound(since=EPOCH + timedelta(seconds=1)) == []


def test_a_retried_message_says_so() -> None:
    store = _store()
    store.record_outbound(SentMessage("SM1", PHONE, "x"), tag=1, seq=0, at=EPOCH)
    store.mark_retried("SM1")
    assert store.pending_outbound(since=EPOCH)[0].retried


def test_a_day_with_no_prices_cost_nothing() -> None:
    assert _store().actual_cost(date(2026, 1, 1)) == (0.0, None)


def test_segments_add_up_per_day() -> None:
    store = _store()
    today = date(2026, 9, 30)
    assert store.segments_on(today) == (0, 0.0)
    store.add_segments(today, 12, 0.672)
    store.add_segments(today, 3, 0.168)
    store.add_segments(today + timedelta(days=1), 1, 0.056)
    used, cost = store.segments_on(today)
    assert used == 15
    assert round(cost, 3) == 0.84


def test_state_is_a_small_key_value_table() -> None:
    store = _store()
    assert store.get_state("missing") is None
    store.set_state("server_tag", "1260")
    store.set_state("server_tag", "1261")
    assert store.get_state("server_tag") == "1261"


def test_purge_drops_everything_older_than_the_cutoff_but_keeps_budget_days() -> None:
    store = _store()
    old, new = EPOCH - timedelta(days=2), EPOCH
    store.record_inbound(InboundMessage("OLD", PHONE, "s", "?", old))
    store.record_inbound(InboundMessage("NEW", PHONE, "s", "?", new))
    old_doc = store.save_document(PHONE, DOC, page_size=12, plain=False, at=old)
    store.link_response(PHONE, 1, old_doc, old)
    store.save_frames(PHONE, 1, {0: "A"}, old)
    store.record_outbound(SentMessage("SM1", PHONE, "x"), tag=1, seq=0, at=old)
    store.add_segments(old.date(), 5, 0.28)
    removed = store.purge(EPOCH - timedelta(days=1))
    assert removed == 5
    assert store.seen_inbound("NEW")
    assert not store.seen_inbound("OLD")
    assert store.document_for(PHONE, 1) is None
    assert store.segments_on(old.date())[0] == 5


def test_timestamps_are_stored_in_utc() -> None:
    store = _store()
    local = datetime(2026, 9, 30, 13, 0, tzinfo=UTC).astimezone()
    store.record_outbound(SentMessage("SM1", PHONE, "x"), tag=None, seq=None, at=local)
    assert store.pending_outbound(since=datetime(2026, 9, 30, 12, 59, tzinfo=UTC))
