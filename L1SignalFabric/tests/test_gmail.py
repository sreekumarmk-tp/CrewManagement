"""Gmail connector: verify, envelope decode, metadata mapping, sign-off, dedup."""

import asyncio
import base64
import json

from connectors.gmail import GmailConnector, message_metadata_to_record, record_to_signal
from connectors.gmail.verify import verify_pubsub_token
from core.connector import InboundRequest
from core.signal import SourceSystem


def _envelope(notif, message_id="p1"):
    data = base64.b64encode(json.dumps(notif).encode()).decode()
    return {"message": {"data": data, "messageId": message_id}}


def test_verify_token_and_dev_bypass():
    assert verify_pubsub_token(configured_token="s3cret", received_token="s3cret").ok
    assert not verify_pubsub_token(configured_token="s3cret", received_token="x").ok
    # dev bypass when no token configured
    c = GmailConnector(tenant_id="t")
    assert c.verify(InboundRequest()).outcome.value == "ok"
    # configured token: rejected when mismatched, ok when matched
    c2 = GmailConnector(tenant_id="t", pubsub_token="s3cret")
    assert c2.verify(InboundRequest(query={})).outcome.value == "reject"
    # Pub/Sub puts the secret on the URL query string (?token=...)
    assert c2.verify(InboundRequest(query={"token": "s3cret"})).outcome.value == "ok"
    # header form is accepted too (proxied deployments)
    assert c2.verify(InboundRequest(query={}, headers={"x-pubsub-token": "s3cret"})).outcome.value == "ok"


def test_metadata_record_extraction_no_body():
    # a format=metadata payload has no body parts → empty body, snippet absent
    msg = {"id": "m1", "threadId": "th1", "internalDate": "1717236000000",
           "labelIds": ["INBOX"], "payload": {"headers": [
               {"name": "From", "value": "a@x"},
               {"name": "To", "value": "b@y, c@z"},
               {"name": "Subject", "value": "Hi"}]}}
    rec = message_metadata_to_record(msg)
    assert rec["from"] == "a@x"
    assert rec["to"] == ["b@y", "c@z"]
    assert rec["body"] == "" and rec["snippet_present"] is False


def test_full_payload_body_extraction():
    # a format=full payload → body decoded from the text/plain part (EMAIL_INGEST_BODY)
    body = "Sign-off: Andreas Pappas (Bosun) - MV Mediterranean Queen at Piraeus"
    b64 = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    msg = {"id": "m2", "threadId": "th2", "internalDate": "1717236000000",
           "labelIds": ["INBOX"], "payload": {
               "mimeType": "multipart/alternative",
               "headers": [{"name": "Subject", "value": "Sign-off"}],
               "parts": [
                   {"mimeType": "text/plain", "body": {"data": b64}},
                   {"mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<p>ignored</p>").decode().rstrip("=")}},
               ]}}
    rec = message_metadata_to_record(msg)
    assert rec["body"] == body and rec["snippet_present"] is True
    # body rides through as the event's ``text`` (the field crew-parsing reads)
    sig = record_to_signal(rec, "t")
    assert sig.data["text"] == body


def test_html_only_body_is_tag_stripped():
    html = "<p>Sign-off: <b>Diego Silva</b> (Oiler) MV Pacific Dawn at Rotterdam</p>"
    b64 = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
    msg = {"id": "m3", "internalDate": "1717236000000", "labelIds": [],
           "payload": {"mimeType": "text/html", "body": {"data": b64}, "headers": []}}
    rec = message_metadata_to_record(msg)
    assert "<" not in rec["body"] and "Diego Silva" in rec["body"]


def test_signoff_intent_set():
    rec = {"message_id": "m", "subject": "Sign-off notification", "to": ["x"]}
    sig = record_to_signal(rec, "t")
    assert sig.metadata.get("l2Intent") == "CREATE_SIGNOFF_EVENT"
    assert sig.source_system == SourceSystem.GMAIL


def test_ingest_envelope_with_inline_messages_and_dedup():
    c = GmailConnector(tenant_id="t")
    notif = {"historyId": "9", "_messages": [
        {"message_id": "mz", "from": "a@x", "to": ["b@y"], "subject": "hi", "labels": [],
         "sent_at": "2024-06-01T10:00:00Z"}]}
    env = _envelope(notif)
    sigs = asyncio.run(c.ingest(env))
    assert len(sigs) == 1 and sigs[0].key == {"message_id": "mz"}
    # same Pub/Sub messageId redelivered → dropped
    assert asyncio.run(c.ingest(env)) == []


def test_history_expansion_with_client_advances_watermark():
    class FakeGmail:
        api_calls = 0
        rate_limit_hits = 0

        def history_list(self, start):
            yield {"id": "100", "messagesAdded": [{"message": {"id": "m1"}}]}

        def get_message(self, mid):
            return {"id": mid, "internalDate": "1717236000000", "labelIds": [],
                    "payload": {"headers": [{"name": "From", "value": "a@x"},
                                            {"name": "Subject", "value": "s"}]}}

    c = GmailConnector(tenant_id="t", client=FakeGmail())
    notif = {"historyId": "200"}
    sigs = asyncio.run(c.ingest(_envelope(notif, "px")))
    assert len(sigs) == 1 and sigs[0].data["from"] == "a@x"
    assert c.position() == "200"
