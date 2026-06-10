"""Outlook (Microsoft Graph mail) client.

Wraps the shared :class:`~connectors.common.graph.GraphClient`. Fetch scope is
controlled by ``ingest_body``:

  * **metadata only** (default) — the ``$select`` allow-list excludes ``body`` and
    ``bodyPreview``: From/To/Cc/Subject/conversation/dates/categories only.
  * **with body** (``ingest_body=True``) — ``body`` + ``bodyPreview`` are added to
    the ``$select`` so the message content is fetched. Enabled by the server via
    the ``EMAIL_INGEST_BODY`` setting.

Supports both a delegated mailbox (``/me/...``) and an app-permission target
mailbox (``/users/{upn}/...``).

Endpoints: mailFolders/{folder}/messages · messages/delta · subscriptions
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Tuple

from connectors.common import GraphClient, StructuredLogger

# Metadata-only projection — body / bodyPreview deliberately excluded.
MAIL_SELECT = ("from,toRecipients,ccRecipients,subject,conversationId,"
               "receivedDateTime,sentDateTime,categories,internetMessageId,isRead")
# Same allow-list plus the message content (server EMAIL_INGEST_BODY on).
MAIL_SELECT_WITH_BODY = MAIL_SELECT + ",body,bodyPreview"


class OutlookClient:
    def __init__(self, graph: GraphClient, *, mailbox: str = "me",
                 ingest_body: bool = False) -> None:
        self.graph = graph
        # "me" → /me ; otherwise a UPN/id → /users/{upn}
        self._root = "me" if mailbox == "me" else f"users/{mailbox}"
        self.ingest_body = ingest_body
        self._select = MAIL_SELECT_WITH_BODY if ingest_body else MAIL_SELECT

    @property
    def api_calls(self) -> int:
        return self.graph.api_calls

    @property
    def rate_limit_hits(self) -> int:
        return self.graph.rate_limit_hits

    def list_messages(self, folder: str = "inbox", top: int = 50,
                      select: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        path = f"{self._root}/mailFolders/{folder}/messages"
        yield from self.graph.iter_collection(
            path, params={"$select": select or self._select, "$top": top})

    def get_message(self, message_id: str, select: Optional[str] = None) -> Dict[str, Any]:
        return self.graph.get(f"{self._root}/messages/{message_id}",
                              params={"$select": select or self._select})

    def delta(self, folder: str = "inbox", *, start: Optional[str] = None,
              select: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
        """Incremental mail sync; ``start`` is a saved deltaLink, else cold start."""
        if start:
            return self.graph.delta(start)
        path = f"{self._root}/mailFolders/{folder}/messages/delta"
        return self.graph.delta(path, params={"$select": select or self._select})

    # --- subscriptions (webhook lifecycle) ---
    def create_subscription(self, *, notification_url: str, client_state: str,
                            resource: str = "me/mailFolders('inbox')/messages",
                            expiration_iso: str,
                            change_type: str = "created") -> Dict[str, Any]:
        return self.graph.post("subscriptions", json={
            "changeType": change_type,
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": expiration_iso,
            "clientState": client_state,
        })

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        return list(self.graph.iter_collection("subscriptions"))

    def delete_subscription(self, subscription_id: str) -> None:
        self.graph.delete(f"subscriptions/{subscription_id}")
