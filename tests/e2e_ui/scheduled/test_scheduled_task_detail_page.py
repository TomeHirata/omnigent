"""UI journey: the Scheduled Task DETAIL page (``/tasks/:taskId``).

Covers the browser path the component tests can't: clicking the task card on
``/tasks`` opens ``/tasks/:taskId`` with the real task, and **Run now** from the
detail header fires ``POST /v1/scheduled-tasks/{id}/run``, records a run in the
background, and the run-history section renders it.

The page ships behind ``automations_v2``, so this module runs its own server with
that feature on: Run now then goes through the claimed-run path the page is
built for. The suite's shared server keeps the legacy scheduler.

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

import os
import signal
import subprocess
import time
from collections.abc import Iterator

import httpx
import pytest
from playwright.sync_api import Page, expect

from omnigent.db.utils import builtin_agent_id
from omnigent.native.native_coding_agents import CLAUDE_NATIVE_AGENT_NAME
from tests._helpers.compat import apply_server_env, compat_server_cwd, server_executable
from tests.e2e_ui.conftest import _BUILD_OUTPUT, _REPO_ROOT, _find_free_port
from tests.e2e_ui.scheduled.test_scheduled_tasks_page import _create_task, _row_by_name

# The dedicated server cold-boots alongside the suite's shared one.
_SERVER_BOOT_TIMEOUT_S = 180.0


@pytest.fixture(scope="module")
def automations_v2_server(
    built_spa: None,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[str]:
    """Spawn a server with ``OMNIGENT_FEATURES=automations_v2`` and yield its URL.

    It starts no runner and connects no host: every Run now here fails at the
    host stage, which is what the journey checks.
    """
    port = _find_free_port()
    server_tmp = tmp_path_factory.mktemp("automations_v2_server")
    log_path = server_tmp / "server.log"
    artifact_dir = server_tmp / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "OMNIGENT_FEATURES": "automations_v2",
        "OMNIGENT_WEB_UI_DIST": str(_BUILD_OUTPUT),
    }
    apply_server_env(env, _REPO_ROOT)
    log_handle = open(log_path, "w")  # noqa: SIM115 — lives for the Popen; closed in finally
    proc = subprocess.Popen(
        [
            server_executable(),
            "-c",
            "from omnigent.cli import main; main()",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--database-uri",
            f"sqlite:///{server_tmp / 'test.db'}",
            "--artifact-location",
            str(artifact_dir),
        ],
        env=env,
        cwd=compat_server_cwd(),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + _SERVER_BOOT_TIMEOUT_S
        ready = False
        last_error = "not polled yet"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                last_error = f"server exited early with code {proc.returncode}"
                break
            try:
                # trust_env=False: a CI HTTP(S) proxy must not intercept loopback.
                if httpx.get(f"{base_url}/health", timeout=2, trust_env=False).status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.5)
        if not ready:
            log_handle.flush()
            raise RuntimeError(
                f"automations_v2 server not healthy within {_SERVER_BOOT_TIMEOUT_S:.0f}s on "
                f"{base_url} (last_error={last_error}).\n{log_path.read_text()[-3000:]}"
            )
        yield base_url
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        log_handle.close()


def test_scheduled_task_detail_page_run_now_records_run_row(
    page: Page,
    automations_v2_server: str,
) -> None:
    """Open a task from the list, then Run now from its header records a run.

    The task has no host and none is connected, so the claimed run fails at the
    host stage. The run-history row shows the stage and reason the server's
    error code maps to, once the background fire lands.

    Icon / tooltip semantics (CalendarOff for skipped, amber triangle for
    failed, etc.) are covered by the RTL unit tests.
    """
    base_url = automations_v2_server
    task_id = _create_task(
        base_url,
        builtin_agent_id(CLAUDE_NATIVE_AGENT_NAME),
        "Detail run-now test",
        "FREQ=DAILY;BYHOUR=9;BYMINUTE=0",
    )

    page.goto(f"{base_url}/tasks")
    row = _row_by_name(page, "Detail run-now test")
    expect(row).to_be_visible(timeout=30_000)
    row.get_by_test_id("task-row-open").click()
    page.wait_for_url(f"**/tasks/{task_id}", timeout=15_000)

    # The detail page loads the real task; component tests cover each field.
    expect(page.get_by_test_id("task-detail-title")).to_have_text(
        "Detail run-now test", timeout=30_000
    )
    expect(page.get_by_test_id("task-detail-schedule")).to_contain_text(
        "Every day at 9:00 AM", timeout=15_000
    )
    expect(page.get_by_test_id("task-detail-host")).to_contain_text("Resolve at fire time")
    expect(page.get_by_test_id("task-detail-runs-empty")).to_be_visible()

    # Run now returns 202; the page polls its run history until the run lands.
    page.get_by_test_id("task-detail-run-now").click()
    run_row = page.get_by_test_id("task-detail-runs").get_by_test_id("task-detail-run").first
    expect(run_row).to_have_attribute("data-run-status", "failed", timeout=30_000)
    expect(run_row.get_by_test_id("run-failure")).to_have_text(
        "Host · None of your hosts was online."
    )
