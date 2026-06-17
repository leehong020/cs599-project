import base64

from app.schemas.gmail import EmailAddress, EmailDraftPayload
from app.services.gmail import (
    build_rfc822_message,
    extract_body_from_payload,
    html_to_text,
    parse_gmail_message,
)


def encode_body(value: str) -> str:
    # Gmail 使用 base64url 编码 MIME part body；测试里复用同样格式。
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def test_html_to_text_keeps_readable_content() -> None:
    result = html_to_text("<div>Hello<br><strong>Mailflow</strong></div>")

    assert "Hello" in result
    assert "Mailflow" in result


def test_extract_body_prefers_plain_text_over_html() -> None:
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": encode_body("<p>HTML Body</p>")},
            },
            {
                "mimeType": "text/plain",
                "body": {"data": encode_body("Plain Body")},
            },
        ],
    }

    result = extract_body_from_payload(payload)

    assert result.text == "Plain Body"
    assert result.html == "<p>HTML Body</p>"


def test_parse_gmail_message_extracts_headers_and_body() -> None:
    raw_message = {
        "id": "msg_1",
        "threadId": "thread_1",
        "snippet": "hello",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "项目更新"},
                {"name": "From", "value": "me@example.com"},
                {"name": "To", "value": "li@example.com"},
            ],
            "mimeType": "text/plain",
            "body": {"data": encode_body("正文")},
        },
    }

    result = parse_gmail_message(raw_message)

    assert result.id == "msg_1"
    assert result.thread_id == "thread_1"
    assert result.subject == "项目更新"
    assert result.to == ["li@example.com"]
    assert result.body.text == "正文"


def test_build_rfc822_reply_keeps_thread_headers() -> None:
    payload = EmailDraftPayload(
        draft_type="reply_email",
        sender_email="me@example.com",
        to=[EmailAddress(email="li@example.com", name="李明")],
        subject="Re: 项目更新",
        body="收到，我会处理。",
        signature_policy="no_signature",
        gmail_thread_id="thread_1",
        reply_to_message_id="<msg_1@example.com>",
    )

    message = build_rfc822_message(payload)

    assert message["In-Reply-To"] == "<msg_1@example.com>"
    assert message["References"] == "<msg_1@example.com>"
    assert "li@example.com" in message["To"]
