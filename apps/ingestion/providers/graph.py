"""Microsoft Graph read-only mailbox provider."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from django.utils.dateparse import parse_datetime

from apps.ingestion.models import MailConnector
from apps.ingestion.providers.base import (
    FetchedMessage,
    MailProviderError,
    ProviderConfigurationError,
)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
TOKEN_ROOT = "https://login.microsoftonline.com"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class MicrosoftGraphMailboxProvider:
    """Read-only Microsoft 365 Outlook provider using Microsoft Graph."""

    def fetch_recent(self, *, connector: MailConnector, limit: int = 25) -> list[FetchedMessage]:
        token = self._access_token(connector)
        mailbox = connector.mailbox_address
        folder = urllib.parse.quote(connector.folder or "Inbox", safe="")
        params = urllib.parse.urlencode(
            {
                "$top": str(limit),
                "$orderby": "receivedDateTime desc",
                "$select": (
                    "id,internetMessageId,conversationId,subject,from,toRecipients,"
                    "receivedDateTime,bodyPreview,body,hasAttachments"
                ),
            }
        )
        url = f"{GRAPH_ROOT}/users/{urllib.parse.quote(mailbox)}/mailFolders/{folder}/messages?{params}"
        # Read-only contract: fetch messages with GET only. Do not mark read,
        # move messages, edit folders, or touch mailbox rules.
        payload = self._get_json(url, token)
        return [self._message_from_graph(item) for item in payload.get("value", [])]

    def _access_token(self, connector: MailConnector) -> str:
        if connector.auth_mode != MailConnector.AuthMode.OAUTH_CLIENT_CREDENTIALS:
            raise ProviderConfigurationError(
                "Microsoft Graph provider currently supports OAuth client credentials."
            )
        config = connector.config or {}
        tenant_id = self._env_value(config, "tenant_id_env")
        client_id = self._env_value(config, "client_id_env")
        client_secret = self._env_value(config, "client_secret_env")
        token_url = f"{TOKEN_ROOT}/{tenant_id}/oauth2/v2.0/token"
        body = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        response = self._open_json(request)
        token = response.get("access_token")
        if not token:
            raise MailProviderError("Microsoft Graph token response did not include access_token.")
        return token

    def _get_json(self, url: str, token: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            method="GET",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - exact urllib exceptions vary.
            raise MailProviderError(f"Microsoft Graph request failed: {exc}") from exc

    def _env_value(self, config: dict[str, Any], key: str) -> str:
        env_name = config.get(key)
        if not env_name:
            raise ProviderConfigurationError(f"Missing connector config key: {key}")
        value = os.environ.get(env_name)
        if not value:
            raise ProviderConfigurationError(f"Environment variable is not set: {env_name}")
        return value

    def _message_from_graph(self, item: dict[str, Any]) -> FetchedMessage:
        sender = ((item.get("from") or {}).get("emailAddress") or {}).get("address", "")
        recipients = [
            (recipient.get("emailAddress") or {}).get("address", "")
            for recipient in item.get("toRecipients", [])
            if (recipient.get("emailAddress") or {}).get("address")
        ]
        received_at = self._parse_graph_datetime(item.get("receivedDateTime"))
        text_body, html_body, html_as_text = self._body_fields(item.get("body"))
        return FetchedMessage(
            external_message_id=item.get("id", ""),
            internet_message_id=item.get("internetMessageId", ""),
            conversation_id=item.get("conversationId", ""),
            subject=item.get("subject", ""),
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            body_preview=item.get("bodyPreview", ""),
            text_body=text_body,
            html_body=html_body,
            html_as_text=html_as_text,
            provider_payload={"graph": item},
            has_attachments=bool(item.get("hasAttachments", False)),
        )

    def _body_fields(self, body: dict[str, Any] | None) -> tuple[str, str, str]:
        if not isinstance(body, dict):
            return "", "", ""
        content = str(body.get("content") or "")
        content_type = str(body.get("contentType") or "").casefold()
        if content_type == "html":
            return "", content, self._html_to_text(content)
        return content, "", ""

    def _html_to_text(self, html: str) -> str:
        parser = _TextExtractor()
        parser.feed(html)
        return parser.text()

    def _parse_graph_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        return parse_datetime(normalized)
