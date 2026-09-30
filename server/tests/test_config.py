from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.conftest import PHONE, SERVER, SERVER_ROOT, build_settings
from textwire.config import (
    InboundMode,
    Settings,
    TransportKind,
    check_for_unknown_env_vars,
    load_settings,
)


def test_defaults_are_safe_to_run_with() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.allowed_numbers == ()
    assert settings.transport is TransportKind.TWILIO
    assert settings.daily_segment_budget == 200
    assert settings.page_frames == 12
    assert settings.debug_drop_once == ()


def test_allowed_numbers_are_read_as_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEXTWIRE_ALLOWED_NUMBERS", f" {PHONE} , +447700900456,, ")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.allowed_numbers == (PHONE, "+447700900456")


def test_allowed_numbers_can_be_given_as_a_tuple() -> None:
    assert build_settings(allowed_numbers=(PHONE,)).allowed_numbers == (PHONE,)


@pytest.mark.parametrize("number", ["07700900123", "+0447700900123", "+44", "+44 7700 900123"])
def test_allowed_numbers_must_be_e164(number: str) -> None:
    with pytest.raises(ValidationError, match=r"E\.164"):
        build_settings(allowed_numbers=(number,))


def test_debug_drop_once_is_read_as_frame_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXTWIRE_DEBUG_DROP_ONCE", "3, 5")
    assert Settings(_env_file=None).debug_drop_once == (3, 5)  # type: ignore[call-arg]


def test_debug_drop_once_can_be_given_as_a_tuple() -> None:
    assert build_settings(debug_drop_once=(0, 254)).debug_drop_once == (0, 254)


def test_debug_drop_once_refuses_numbers_outside_a_response() -> None:
    with pytest.raises(ValidationError, match="not a frame number"):
        build_settings(debug_drop_once=(255,))


def test_page_frames_cannot_exceed_the_maximum() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        build_settings(page_frames=20, max_page_frames=10)


def test_twilio_number_must_be_e164() -> None:
    with pytest.raises(ValidationError, match="TEXTWIRE_TWILIO_NUMBER"):
        build_settings(twilio_number="07700900000")


def test_secrets_never_appear_in_validation_errors() -> None:
    with pytest.raises(ValidationError) as caught:
        build_settings(twilio_auth_token="hunter2-secret", page_frames=0)
    assert "hunter2-secret" not in str(caught.value)


def test_settings_are_frozen() -> None:
    settings = build_settings()
    with pytest.raises(ValidationError):
        settings.page_frames = 3


def test_database_lives_in_the_data_directory(tmp_path: Path) -> None:
    assert build_settings(data_dir=tmp_path).database_path == tmp_path / "textwire.db"


def test_a_complete_twilio_configuration_has_no_problems() -> None:
    assert build_settings().transport_problems() == []


def test_twilio_problems_name_every_missing_variable() -> None:
    settings = build_settings(
        twilio_account_sid="", twilio_auth_token="", twilio_number="", allowed_numbers=()
    )
    assert settings.transport_problems() == [
        "TEXTWIRE_TWILIO_ACCOUNT_SID is not set",
        "TEXTWIRE_TWILIO_AUTH_TOKEN is not set",
        "TEXTWIRE_TWILIO_NUMBER is not set",
        "TEXTWIRE_ALLOWED_NUMBERS is empty, so every request is ignored",
    ]


def test_webhook_mode_needs_a_public_url() -> None:
    settings = build_settings(inbound=InboundMode.WEBHOOK)
    assert settings.transport_problems() == ["TEXTWIRE_PUBLIC_BASE_URL is not set"]
    ready = build_settings(inbound=InboundMode.WEBHOOK, public_base_url="https://sms.example")
    assert ready.transport_problems() == []


def test_gateway_problems_name_every_missing_variable() -> None:
    settings = build_settings(transport=TransportKind.GATEWAY)
    assert settings.transport_problems() == [
        "TEXTWIRE_GATEWAY_URL is not set",
        "TEXTWIRE_GATEWAY_USERNAME is not set",
        "TEXTWIRE_GATEWAY_PASSWORD is not set",
    ]
    ready = build_settings(
        transport=TransportKind.GATEWAY,
        gateway_url="http://192.0.2.10:8080",
        gateway_username="sms",
        gateway_password="pw",
    )
    assert ready.transport_problems() == []


def test_unknown_variables_under_the_prefix_are_refused() -> None:
    with pytest.raises(RuntimeError, match="TEXTWIRE_PAGE_FRAME, TEXTWIRE_TYPO"):
        check_for_unknown_env_vars(
            {"TEXTWIRE_TYPO": "1", "TEXTWIRE_PAGE_FRAME": "3", "TEXTWIRE_PAGE_FRAMES": "3"}
        )


def test_other_variables_are_ignored() -> None:
    check_for_unknown_env_vars({"PATH": "/bin", "TEXTWIRE_PORT": "1"})


def test_load_settings_reads_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEXTWIRE_PAGE_FRAMES", "8")
    assert load_settings().page_frames == 8


def test_load_settings_refuses_a_typo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEXTWIRE_PAGEFRAMES", "8")
    with pytest.raises(RuntimeError, match="TEXTWIRE_PAGEFRAMES"):
        load_settings()


def test_load_settings_reads_a_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"TEXTWIRE_TWILIO_NUMBER={SERVER}\n", encoding="utf-8")
    assert load_settings().twilio_number == SERVER


def test_the_example_environment_file_is_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    shutil.copy(SERVER_ROOT / ".env.example", tmp_path / ".env")
    assert load_settings() == Settings(_env_file=None)  # type: ignore[call-arg]


def test_the_example_environment_file_documents_every_setting() -> None:
    example = (SERVER_ROOT / ".env.example").read_text(encoding="utf-8")
    missing = [name for name in Settings.model_fields if f"TEXTWIRE_{name.upper()}=" not in example]
    assert missing == []
