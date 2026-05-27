"""
Notification Agent — sends real email notifications to captain and crew over SMTP.
Tools: sendMail(), createNotificationLog()

sendMail delivers via SMTP (defaults to MailHog in dev — see config.smtp_*). The
tool runs locally in our orchestrator when the hosted agent emits the
`agent.custom_tool_use` event, so the actual send happens here, not on Anthropic's side.
"""
import asyncio
import re
import smtplib
import uuid
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List

import structlog

from agents.base_agent import BaseAgent
from config import settings

log = structlog.get_logger()

TOOLS = [
    {
        "name": "sendMail",
        "description": (
            "Send an email notification over SMTP and return the delivery receipt. "
            "Recipient may be an email address or a role/name (e.g. 'Captain', "
            "'Shore Manager') — names are routed to a deliverable address automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email or name"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "Email priority level",
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attachment names",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "createNotificationLog",
        "description": "Create a structured log entry for all sent notifications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "notification_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of notification IDs to log",
                },
                "workflow_id": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["notification_ids", "workflow_id"],
        },
    },
]

SYSTEM_ROLE = """You are the Notification Agent for a maritime crew management system.
Your job is to send appropriate notifications to all relevant parties about the crew sign-off/sign-on process.

You MUST send notifications to:
1. The Captain — crew sign-off initiated + replacement selected + travel details
2. The Shore Manager — operational update
3. The signing-off crew member — farewell and travel info
4. The joining crew member — welcome and joining instructions

Use sendMail() for each notification, then createNotificationLog() to record all sent messages.
Be professional and maritime-industry-appropriate in all communications."""


class NotificationAgent(BaseAgent):
    def __init__(self, event_callback=None):
        super().__init__(
            name="Notification Agent",
            role=SYSTEM_ROLE,
            tools=TOOLS,
            event_callback=event_callback,
        )
        self._sent_notifications: List[Dict[str, Any]] = []

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        if tool_name == "sendMail":
            return await self._send_mail(tool_input)
        if tool_name == "createNotificationLog":
            return self._create_notification_log(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _to_address(self, recipient: str) -> str:
        """Resolve a recipient to a deliverable address. Pass through real
        addresses; turn a role/name into <slug>@<mail_default_domain>."""
        recipient = (recipient or "").strip()
        if "@" in recipient:
            return recipient
        slug = re.sub(r"[^a-z0-9]+", ".", recipient.lower()).strip(".") or "crew"
        return f"{slug}@{settings.mail_default_domain}"

    @staticmethod
    def _smtp_send(msg: EmailMessage) -> None:
        """Blocking SMTP send — run via asyncio.to_thread so it can't stall the loop."""
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)

    async def _send_mail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        notification_id = f"NTF-{uuid.uuid4().hex[:8].upper()}"
        display_to = params.get("to")
        to_email = self._to_address(display_to)
        subject = params.get("subject", "(no subject)")
        body = params.get("body", "")
        priority = params.get("priority", "normal")
        attachments = params.get("attachments", []) or []

        body_text = body
        if attachments:
            body_text += "\n\n--\nAttachments: " + ", ".join(attachments)

        status, channel, error = "Delivered", "Email (SMTP)", None
        if not settings.mail_enabled:
            status, channel = "Skipped", "Email (disabled)"
        else:
            msg = EmailMessage()
            msg["From"] = settings.smtp_from
            msg["To"] = to_email
            msg["Subject"] = subject
            if priority in ("high", "urgent"):
                msg["X-Priority"] = "1"
                msg["Importance"] = "high"
            msg.set_content(body_text)
            try:
                await asyncio.to_thread(self._smtp_send, msg)
                log.info("notification.sent", to=to_email, subject=subject, notification_id=notification_id)
            except Exception as exc:  # don't fail the workflow on a mail hiccup
                status, channel, error = "Failed", "Email (SMTP, failed)", str(exc)
                log.error("notification.send_failed", to=to_email, error=str(exc))

        record = {
            "notification_id": notification_id,
            "to": display_to,
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "priority": priority,
            "attachments": attachments,
            "sent_at": datetime.utcnow().isoformat(),
            "status": status,
            "channel": channel,
            "delivery_receipt": f"RCPT-{uuid.uuid4().hex[:6].upper()}",
        }
        if error:
            record["error"] = error
        self._sent_notifications.append(record)

        result = {
            "notification_id": notification_id,
            "status": status,
            "to": to_email,
            "message": (
                f"Email sent to {to_email}" if status == "Delivered"
                else f"Email {status.lower()} for {to_email}"
            ),
            "timestamp": record["sent_at"],
        }
        if error:
            result["error"] = error
        return result

    def _create_notification_log(self, params: Dict[str, Any]) -> Dict[str, Any]:
        log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
        return {
            "log_id": log_id,
            "workflow_id": params.get("workflow_id"),
            "total_notifications": len(self._sent_notifications),
            "notification_ids": params.get("notification_ids", []),
            "summary": params.get("summary", "All notifications dispatched successfully."),
            "logged_at": datetime.utcnow().isoformat(),
        }

    async def _validate_and_format(
        self, raw_text: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.execution.confidence_score = 0.99
        return {
            "notifications_sent": self._sent_notifications,
            "total_count": len(self._sent_notifications),
            "narrative": raw_text[:500] if raw_text else "All notifications dispatched.",
        }
