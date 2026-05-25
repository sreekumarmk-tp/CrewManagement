"""
Notification Agent — sends mock email/notification alerts to captain and crew.
Tools: sendMail(), createNotificationLog()
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List

from agents.base_agent import BaseAgent

TOOLS = [
    {
        "name": "sendMail",
        "description": (
            "Send a mock email notification. Returns a mock delivery receipt. "
            "Does NOT send real email — simulation only."
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
            return self._send_mail(tool_input)
        if tool_name == "createNotificationLog":
            return self._create_notification_log(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    def _send_mail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        notification_id = f"NTF-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "notification_id": notification_id,
            "to": params.get("to"),
            "subject": params.get("subject"),
            "body": params.get("body"),
            "priority": params.get("priority", "normal"),
            "attachments": params.get("attachments", []),
            "sent_at": datetime.utcnow().isoformat(),
            "status": "Delivered",
            "channel": "Email (Mock)",
            "delivery_receipt": f"RCPT-{uuid.uuid4().hex[:6].upper()}",
        }
        self._sent_notifications.append(record)
        return {
            "notification_id": notification_id,
            "status": "Delivered",
            "message": f"Email successfully sent to {params.get('to')}",
            "timestamp": record["sent_at"],
        }

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
