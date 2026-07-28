"""Gmail integration client.

The client validates OAuth configuration, sends outbound outreach, and exposes
message/thread data needed by CRM synchronization without leaking Gmail-specific
details into route handlers.
"""

from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


@dataclass(frozen=True)
class GmailSendResult:
    message_id: str
    thread_id: str


@dataclass(frozen=True)
class GmailReplyMessage:
    gmail_message_id: str
    message_id_header: str
    references_header: str
    from_email: str


@dataclass(frozen=True)
class GmailThreadMessage:
    gmail_message_id: str
    gmail_thread_id: str
    message_id_header: str
    references_header: str
    from_email: str
    to_email: str
    subject: str
    body_text: str
    body_html: str
    snippet: str
    message_at: datetime


class GmailConfigurationError(RuntimeError):
    pass


class GmailSendError(RuntimeError):
    pass


class GmailClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sender_email: str = "",
    ) -> None:
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=GMAIL_SCOPES,
            )
            creds.refresh(Request())
            self.service = build(
                "gmail",
                "v1",
                credentials=creds,
                cache_discovery=False,
            )
            profile = self.service.users().getProfile(userId="me").execute()
        except RefreshError as exc:
            raise GmailConfigurationError(
                "Gmail authorization is invalid or expired. "
                "Reconnect Gmail in Settings."
            ) from exc
        except Exception as exc:
            raise GmailConfigurationError(
                "Gmail configuration could not be verified. "
                "Check the client ID, client secret, refresh token, and Gmail API access."
            ) from exc

        profile_email = str(profile.get("emailAddress", "")).strip()
        self.sender_email = sender_email.strip() or profile_email
        self.profile_email = profile_email

    def validate_configuration(self) -> None:
        if not _valid_email(self.profile_email):
            raise GmailConfigurationError(
                "Gmail account validation did not return a sender email address."
            )
        if not _valid_email(self.sender_email):
            raise GmailConfigurationError(
                "Gmail sender email is invalid. Reconnect Gmail in Settings."
            )

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        tracking_pixel_url: str | None = None,
    ) -> GmailSendResult:
        if not _valid_email(to_email):
            raise RuntimeError("Cannot send email: lead has no email address.")
        if not subject.strip():
            raise RuntimeError("Cannot send email: subject line is empty.")
        if not body.strip():
            raise RuntimeError("Cannot send email: selected outreach draft is empty.")

        message = EmailMessage()
        message["To"] = to_email
        if self.sender_email:
            message["From"] = self.sender_email
        message["Subject"] = subject
        message.set_content(body)

        html_body = "<br>".join(html.escape(line) for line in body.splitlines())
        if tracking_pixel_url:
            html_body += (
                f'<img src="{html.escape(tracking_pixel_url)}" width="1" height="1" '
                'style="display:none" alt="" />'
            )
        message.add_alternative(html_body, subtype="html")

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        try:
            sent = self.service.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()
        except HttpError as exc:
            raise GmailSendError(
                "Gmail rejected the message. Verify Gmail API access, sender permissions, "
                "and recipient details."
            ) from exc
        except Exception as exc:
            raise GmailSendError(
                "Gmail could not send the message. "
                "Check the Gmail configuration and try again."
            ) from exc
        return GmailSendResult(message_id=sent.get("id", ""), thread_id=sent.get("threadId", ""))

    def send_thread_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str,
        in_reply_to: str = "",
        references: str = "",
    ) -> GmailSendResult:
        if not to_email:
            raise RuntimeError("Cannot send reply: lead has no email address.")
        if not thread_id:
            raise RuntimeError("Cannot send reply: Gmail thread id is missing.")

        message = EmailMessage()
        message["To"] = to_email
        if self.sender_email:
            message["From"] = self.sender_email
        clean_subject = subject.strip() or "Your message"
        message["Subject"] = clean_subject if clean_subject.lower().startswith("re:") else f"Re: {clean_subject}"
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = " ".join(filter(None, [references, in_reply_to]))
        message.set_content(body)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        sent = self.service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id},
        ).execute()
        return GmailSendResult(message_id=sent.get("id", ""), thread_id=sent.get("threadId", thread_id))

    def thread_has_reply(self, thread_id: str, sender_email: str, recipient_email: str) -> bool:
        return self.thread_reply_message(thread_id, sender_email, recipient_email) is not None

    def thread_messages(self, thread_id: str) -> list[GmailThreadMessage]:
        if not thread_id:
            return []
        thread = self.service.users().threads().get(
            userId="me",
            id=thread_id,
            format="full",
        ).execute()
        messages: list[GmailThreadMessage] = []
        for message in thread.get("messages", []):
            payload = message.get("payload", {})
            headers = payload.get("headers", [])
            header_map = {
                header.get("name", "").lower(): header.get("value", "")
                for header in headers
            }
            body_text, body_html = _message_bodies(payload)
            internal_date = int(message.get("internalDate", "0") or 0)
            messages.append(
                GmailThreadMessage(
                    gmail_message_id=message.get("id", ""),
                    gmail_thread_id=thread_id,
                    message_id_header=header_map.get("message-id", ""),
                    references_header=header_map.get("references", ""),
                    from_email=_email_address(header_map.get("from", "")),
                    to_email=_email_address(header_map.get("to", "")),
                    subject=header_map.get("subject", ""),
                    body_text=body_text,
                    body_html=body_html,
                    snippet=message.get("snippet", ""),
                    message_at=datetime.fromtimestamp(
                        internal_date / 1000,
                        tz=timezone.utc,
                    ),
                )
            )
        return sorted(messages, key=lambda item: item.message_at)

    def thread_reply_message(
        self,
        thread_id: str,
        sender_email: str,
        recipient_email: str,
    ) -> GmailReplyMessage | None:
        if not thread_id or not recipient_email:
            return None
        thread = self.service.users().threads().get(userId="me", id=thread_id, format="metadata").execute()
        recipient_lower = _email_address(recipient_email)
        sender_lower = _email_address(sender_email)
        latest: GmailReplyMessage | None = None
        latest_date = -1
        for message in thread.get("messages", []):
            headers = message.get("payload", {}).get("headers", [])
            header_map = {
                header.get("name", "").lower(): header.get("value", "")
                for header in headers
            }
            from_email = _email_address(header_map.get("from", ""))
            if from_email != recipient_lower or from_email == sender_lower:
                continue
            internal_date = int(message.get("internalDate", "0") or 0)
            if internal_date >= latest_date:
                latest_date = internal_date
                latest = GmailReplyMessage(
                    gmail_message_id=message.get("id", ""),
                    message_id_header=header_map.get("message-id", ""),
                    references_header=header_map.get("references", ""),
                    from_email=from_email,
                )
        return latest


def _email_address(value: str) -> str:
    return (parseaddr(value)[1] or value).strip().lower()


def _valid_email(value: str) -> bool:
    address = _email_address(value)
    local, separator, domain = address.rpartition("@")
    return bool(separator and local and "." in domain and not domain.startswith("."))


def _message_bodies(payload: dict[str, Any]) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict[str, Any]) -> None:
        mime_type = str(part.get("mimeType", "")).lower()
        data = part.get("body", {}).get("data", "")
        if data:
            decoded = _decode_body(data)
            if mime_type == "text/plain":
                text_parts.append(decoded)
            elif mime_type == "text/html":
                html_parts.append(decoded)
        for child in part.get("parts", []) or []:
            visit(child)

    visit(payload)
    return "\n".join(text_parts).strip(), "\n".join(html_parts).strip()


def _decode_body(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""
