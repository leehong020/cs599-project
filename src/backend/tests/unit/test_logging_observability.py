import logging

import pytest

from app.core.logging import audit_log_event, configure_logging, redact_text


def test_redact_text_masks_tokens_and_sensitive_body() -> None:
    value = {
        "access_token": "token-secret",
        "body": "完整邮件正文不能进入日志。",
        "nested": {"client_secret": "client-secret"},
    }

    redacted = redact_text(value)

    assert "token-secret" not in redacted
    assert "完整邮件正文" not in redacted
    assert "client-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_configured_logging_redacts_runtime_messages(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging()
    logger = logging.getLogger("mailflow.stage10")

    with caplog.at_level(logging.INFO, logger="mailflow.stage10"):
        logger.info(
            "access_token=token-secret refresh_token=refresh-secret "
            "Authorization: Bearer bearer-secret"
        )

    assert "token-secret" not in caplog.text
    assert "refresh-secret" not in caplog.text
    assert "bearer-secret" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_audit_log_event_keeps_only_allowlisted_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging()

    with caplog.at_level(logging.INFO, logger="mailflow.audit"):
        audit_log_event(
            "proposal.created",
            proposal_item_id="pi_stage10",
            action_type="send_email",
            status="awaiting_confirmation",
            body="完整邮件正文不能进入审计日志。",
            access_token="token-secret",
        )

    assert "pi_stage10" in caplog.text
    assert "send_email" in caplog.text
    assert "完整邮件正文" not in caplog.text
    assert "token-secret" not in caplog.text
