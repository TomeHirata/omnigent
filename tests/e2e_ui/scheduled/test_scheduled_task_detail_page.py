"""UI journey: the Scheduled Task DETAIL page (``/tasks/:taskId``).

Covers the core detail-page render + interaction path for a scheduled task:

* The detail page renders the task's name, prompt, Configuration block
  (agent + host), and the status line (pause toggle + Active/Paused pill +
  human-readable schedule).
* Clicking the task card on ``/tasks`` navigates to ``/tasks/:taskId``.
* Triggering **Run now** from the detail header fires
  ``POST /v1/scheduled-tasks/{id}/run``, records a run in the background,
  and the run-history section renders a run row.

The seeded task pins no host, so a manual Run now with no online host records
a ``failed`` run (``no_online_host``). This exercises the end-to-end render
path without needing a live host or an agent turn, exactly like
``test_scheduled_task_row_run_controls`` in the sibling test file.

**Icon / tooltip semantics are NOT re-tested here.** The CalendarOff-for-skipped
icon, the amber triangle for failed runs, the unread blue dot, and all tooltip
text are already covered by the RTL unit tests in
``web/src/pages/TaskDetailPage.test.tsx``.

This E2E test focuses on the render + navigation + run-now → run-row journey
that only the live server path can exercise.
"""

from __future__ import annotations

import httpx
from playwright.sync_api import Page, expect

from tests.e2e_ui.scheduled.test_scheduled_tasks_page import (
    _builtin_agent_id,
    _create_task,
    # Autouse: the session-wide live server would otherwise keep these tests'
    # tasks, and the list-page tests count rows.
    _delete_scheduled_tasks_created_by_test,  # noqa: F401
    _row_by_name,
)


def test_scheduled_task_detail_page_renders_header_and_sections(
    page: Page,
    live_server: str,
) -> None:
    """Navigating to a task card lands on the detail page with all key sections.

    Asserts the title, prompt, Configuration block (agent + host), and the
    status line (Active pill + pause toggle + schedule summary) all render.
    """
    agent_id = _builtin_agent_id(live_server, "hello_world")
    _create_task(
        live_server,
        agent_id,
        "Detail render test",
        "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
    )

    page.goto(f"{live_server}/tasks")
    row = _row_by_name(page, "Detail render test")
    expect(row).to_be_visible(timeout=30_000)

    # Click the card body to navigate to the detail page.
    row.get_by_test_id("task-row-open").click()

    # URL must change to /tasks/:id.
    page.wait_for_url("**/tasks/**", timeout=15_000)

    # Header: task name.
    expect(page.get_by_test_id("task-detail-title")).to_have_text(
        "Detail render test", timeout=30_000
    )

    # Status line: Active pill, pause toggle, schedule summary.
    expect(page.get_by_test_id("task-detail-state-pill")).to_contain_text("Active")
    expect(page.get_by_test_id("task-detail-pause-toggle")).to_be_visible()
    # The schedule summary is derived client-side from the stored RRULE.
    expect(page.get_by_test_id("task-detail-schedule")).to_contain_text(
        "Every day at 9:00 AM", timeout=15_000
    )

    # Prompt section.
    expect(page.get_by_test_id("task-detail-prompt")).to_be_visible()

    # Configuration block: the agent label resolves; the host reads
    # "Resolve at fire time" when no host_id is pinned.
    expect(page.get_by_test_id("task-detail-agent")).to_be_visible()
    expect(page.get_by_test_id("task-detail-host")).to_contain_text("Resolve at fire time")

    # Back link navigates back to the list.
    expect(page.get_by_test_id("task-detail-back")).to_be_visible()


def test_scheduled_task_detail_page_run_now_records_run_row(
    page: Page,
    live_server: str,
) -> None:
    """Run now from the detail header fires the task and a run row appears.

    The seeded task has no host, so the fire records a ``failed`` run (no
    online host at fire time). This exercises the real
    ``POST /v1/scheduled-tasks/{id}/run`` path from the detail page and
    confirms the run-history row shows the stage and reason the server's
    error code maps to, once the background fire lands.

    Icon / tooltip semantics (CalendarOff for skipped, amber triangle for
    failed, etc.) are covered by the RTL unit tests.
    """
    agent_id = _builtin_agent_id(live_server, "hello_world")
    task_id = _create_task(
        live_server,
        agent_id,
        "Detail run-now test",
        "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
    )

    page.goto(f"{live_server}/tasks")
    row = _row_by_name(page, "Detail run-now test")
    expect(row).to_be_visible(timeout=30_000)
    row.get_by_test_id("task-row-open").click()
    page.wait_for_url("**/tasks/**", timeout=15_000)

    # Confirm the detail page loaded.
    expect(page.get_by_test_id("task-detail-title")).to_have_text(
        "Detail run-now test", timeout=30_000
    )

    # No run has fired yet.
    pre = httpx.get(f"{live_server}/v1/scheduled-tasks/{task_id}/runs", timeout=10.0)
    assert pre.json()["runs"] == [], "expected empty run history before Run now"

    # Trigger Run now from the detail-page header button.
    page.get_by_test_id("task-detail-run-now").click()

    # The POST returns 202; the actual run is written by a background task.
    # Poll the API until the run is recorded (mirrors the sibling list-page test).
    def _has_run() -> bool:
        runs = httpx.get(f"{live_server}/v1/scheduled-tasks/{task_id}/runs", timeout=10.0).json()[
            "runs"
        ]
        return len(runs) >= 1

    deadline = 0
    while not _has_run() and deadline < 100:
        page.wait_for_timeout(200)
        deadline += 1
    assert _has_run(), "Run now did not record a run within the timeout"

    # After the run is written the page's polling query (useScheduledTaskRuns)
    # re-fetches and the run-history row explains the failure.
    expect(page.get_by_test_id("task-detail-runs")).to_be_visible(timeout=30_000)
    run_row = page.get_by_test_id("task-detail-runs").get_by_test_id("task-detail-run").first
    expect(run_row).to_have_attribute("data-run-status", "failed", timeout=30_000)
    expect(run_row.get_by_test_id("run-failure")).to_have_text(
        "Host · None of your hosts was online."
    )
