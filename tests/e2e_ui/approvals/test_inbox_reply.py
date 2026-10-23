"""E2E: reply to a session from its unread Inbox row.

Verifies the reply reaches the agent as a user message, the row clears on
send, and the agent's answer brings it back as a new unread reply.
"""

from __future__ import annotations

import re
import time
import uuid

import httpx
from playwright.sync_api import Page, expect

from tests.e2e_ui.conftest import configure_mock_llm

_UNREAD_ROW = '[data-testid="inbox-unread"]'
_FIRST_REPLY = "Refactor finished: 3 files changed, all tests green."
_ANSWER = "Added the missing migration and re-ran the suite."
_TURN_TIMEOUT_MS = 60_000


def _send_user_message(base_url: str, session_id: str, text: str) -> None:
    """Start a turn through the events API, as another client would.

    :param base_url: Live server base URL.
    :param session_id: Session to message.
    :param text: User message text.
    """
    httpx.post(
        f"{base_url}/v1/sessions/{session_id}/events",
        json={
            "type": "message",
            "data": {"role": "user", "content": [{"type": "input_text", "text": text}]},
        },
        timeout=30.0,
    ).raise_for_status()


def test_reply_from_inbox_reaches_the_agent(
    page: Page,
    seeded_session: tuple[str, str],
    mock_llm_server_url: str,
) -> None:
    """A reply typed in the Inbox runs a turn and its answer re-surfaces the row."""
    base_url, session_id = seeded_session
    first_marker = f"inbox-reply-{uuid.uuid4().hex[:8]}"
    reply_marker = f"inbox-reply-{uuid.uuid4().hex[:8]}"
    # Several copies per marker so a title-generation call matching the same
    # prompt can't drain the queue before the agent's turn.
    configure_mock_llm(mock_llm_server_url, [{"text": _FIRST_REPLY}] * 3, match=first_marker)
    # Read-state compares whole-second `updated_at`, so an answer landing in
    # the same second as the reply would count as read; real models are slower.
    configure_mock_llm(
        mock_llm_server_url, [{"text": _ANSWER, "delay": 2.0}] * 3, match=reply_marker
    )

    page.goto(f"{base_url}/inbox")
    expect(page.get_by_text("Nothing waiting on you")).to_be_visible(timeout=30_000)

    # Let `updated_at` (whole seconds) move past the read-as-of-load baseline.
    time.sleep(1.1)
    _send_user_message(base_url, session_id, f"Summarize the refactor. Marker: {first_marker}")

    row = page.locator(_UNREAD_ROW)
    expect(row).to_be_visible(timeout=_TURN_TIMEOUT_MS)
    expect(row).to_contain_text(_FIRST_REPLY, timeout=15_000)
    row.locator("button[aria-expanded]").click()

    reply = f"Add the missing migration too. Marker: {reply_marker}"
    box = row.get_by_role("textbox", name=re.compile(r"^Reply to "))
    box.press_sequentially(reply)
    row.get_by_role("button", name="Send").click()

    # Replying is reading: the row clears at once, with a confirmation.
    expect(page.get_by_test_id("toast").filter(has_text="Reply sent to")).to_be_visible()
    expect(row).to_have_count(0)

    # The agent's answer lights the row again.
    expect(row).to_be_visible(timeout=_TURN_TIMEOUT_MS)
    expect(row).to_contain_text(_ANSWER, timeout=15_000)

    row.locator("button[aria-expanded]").click()
    expect(row.get_by_role("textbox", name=re.compile(r"^Reply to "))).to_have_value("")
    row.get_by_role("link", name="Open session").click()
    expect(page).to_have_url(re.compile(rf"/c/{re.escape(session_id)}"))
    bubbles = page.locator('[data-testid="message-bubble"]')
    expect(bubbles.filter(has_text=reply)).to_be_visible(timeout=30_000)
    expect(bubbles.filter(has_text=_ANSWER)).to_be_visible(timeout=30_000)
