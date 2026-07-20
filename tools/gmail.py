"""
Gmail draft tool — opens a pre-filled Gmail compose window in the default browser.

No OAuth or API keys required. Builds a Gmail compose URL and opens it via
webbrowser.open(), which uses whatever the OS default browser is.

Registered as an agent tool only when ENABLE_GMAIL_DRAFT = True in config.py.
"""

from __future__ import annotations

import urllib.parse
import webbrowser


def draft_email(to: str = "", subject: str = "", body: str = "") -> str:
    """
    Open a Gmail compose window in the default browser with pre-filled fields.

    Args:
        to: Recipient email address (optional).
        subject: Email subject line (optional).
        body: Email body text (optional).

    Returns:
        Confirmation message.
    """
    params: dict[str, str] = {
        "view": "cm",
        "fs": "1",
    }
    if to:
        params["to"] = to
    if subject:
        params["su"] = subject
    if body:
        params["body"] = body

    gmail_url = "https://mail.google.com/mail/?" + urllib.parse.urlencode(params)
    webbrowser.open(gmail_url)

    parts = []
    if to:
        parts.append(f"To: {to}")
    if subject:
        parts.append(f"Subject: {subject}")
    summary = ", ".join(parts) if parts else "blank draft"
    return f"Gmail compose window opened in browser ({summary})."


# ── Tool schema ───────────────────────────────────────────────────────────────

TOOL_SCHEMAS_GMAIL = [
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": (
                "Open a Gmail compose window in the default browser with pre-filled fields. "
                "All fields are optional — omit any that are not needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body text.",
                    },
                },
                "required": [],
            },
        },
    },
]
