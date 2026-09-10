import httpx
import pytest

from services.tatva_notify import (
    EmailSendError,
    build_notification_body,
    notification_send_url,
    outbound_quote_number,
    send_ask_vendor_email,
)


def test_outbound_quote_number_keeps_one_id():
    assert outbound_quote_number("#Q3O387V, #QDTP2MV") == "Q3O387V"
    assert outbound_quote_number("Q2OE1CX") == "Q2OE1CX"


def test_build_notification_body_uses_html_list(monkeypatch):
    monkeypatch.setenv("TATVA_API_BASE", "https://testopsapi.withtatva.ai")
    body = build_notification_body(
        email=" Quotes@Vendor.COM ",
        vendor_name="Example Vendor",
        quote_number="#Q-123, #Q-OTHER",
        questions=["Confirm GST.", "List package contents."],
        notes="Please reply by Friday.",
    )
    assert body["type"] == "generic"
    assert body["to"] == "quotes@vendor.com"
    assert body["data"]["subject"] == "Clarifications for quote Q-123"
    html = body["data"]["html"]
    assert "<ol>" in html
    assert "<li>Confirm GST.</li>" in html
    assert "1. 1." not in html
    assert "Q-OTHER" not in html
    assert "Notes:" in html


def test_rejects_invalid_recipient():
    with pytest.raises(EmailSendError, match="No usable vendor email"):
        build_notification_body(
            email="not-an-email",
            vendor_name="Vendor",
            quote_number="Q-1",
            questions=["Confirm GST."],
        )


def test_send_posts_to_tatva_api_base(monkeypatch):
    monkeypatch.setenv("TATVA_API_BASE", "https://opsapi.withtatva.ai")
    monkeypatch.setenv("TATVA_API_KEY", "test-key")
    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "success": True,
                "message": "Generic notification sent successfully",
                "type": "generic",
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    result = send_ask_vendor_email(
        email="quotes@vendor.com",
        vendor_name="Vendor",
        quote_number="Q-1",
        questions=["Confirm GST."],
    )
    assert captured["url"] == "https://opsapi.withtatva.ai/notification/api/notifications/send"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["json"]["to"] == "quotes@vendor.com"
    assert "from" not in captured["json"]
    assert result["ok"] is True
    assert notification_send_url() == captured["url"]
