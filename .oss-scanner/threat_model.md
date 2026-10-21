# Threat model

Read by Anthropic's OSS Scanner before it audits Omnigent. Policy details are in `docs/POLICIES.md`; auth,
credential and sandbox designs are in `designs/` (`CLIENT_CREDENTIALS.md`, `CREDENTIAL_STORE.md`,
`DEVICE_AUTH.md`, `SANDBOX_CREDENTIAL_PROXY.md`).

## What this project does and where untrusted input enters

Omnigent is a meta-harness for coding agents. A **server** (`omnigent/server/`, FastAPI + WebSockets)
stores sessions and coordinates them. **Hosts** (`omnigent/host/`, `omnigent/runner/`) run on a user's
machine or in a cloud sandbox, dial the server over a WebSocket tunnel (`omnigent/server/routes/host_tunnel.py`,
`runner_tunnel.py`), and launch agent **harnesses** (Claude Code, Codex, Cursor and others, `omnigent/harnesses/`)
that read files and run commands on that host. Users drive sessions from the web UI (`web/src/`), the
Electron desktop app (`web/electron/`), the mobile apps (`web/ios/`, `web/android/`), the CLI and the SDKs
(`sdks/`).

There are two deployment modes, and the trust model differs between them:

- **Single-user local**: `omnigent server` on loopback with `OMNIGENT_LOCAL_SINGLE_USER=1`. Requests
  without credentials are served as the reserved `local` user. This is intentional; there is one user.
- **Multi-user server**: `OMNIGENT_AUTH_ENABLED=1`. Identity comes from the built-in `accounts` provider
  (username and password, invite-only, the first user is admin), `oidc` (authorization code + PKCE), or
  `header` (a trusted upstream proxy sets `X-Forwarded-Email` or `OMNIGENT_AUTH_HEADER`). Selection is in
  `resolve_auth_source()` in `omnigent/server/auth.py`. **This is the mode we care most about.**

The roles, from most to least trusted:

- **Server operator / admin**: deploys and configures the server, its config YAML, server-wide policies
  and `policy_modules` (arbitrary Python). Fully trusted. Admins can open every session.
- **Session owner**: owns sessions and the hosts they registered. Their agents run with their privileges on
  their hosts.
- **Collaborators**: users granted read (1), edit (2) or manage (3) on a session
  (`omnigent/stores/permission_store/`, `LEVEL_*` in `omnigent/server/auth.py`). Public sharing is the
  `__public__` grant, limited by `OMNIGENT_SHARING_MODE`.
- **Other authenticated users** of the same server: no access to sessions, hosts, files or credentials
  they have not been granted.
- **Hosts and managed sandboxes**: authenticate the tunnel as their owner, or with a managed-host launch
  token. They are trusted only for the sessions bound to them.
- **Agent output, tool results, fetched web pages, repository contents and MCP server responses**: untrusted.
  They may carry prompt injection.
- **Unauthenticated network clients** reaching the server.

The defects we want found cross one of these boundaries:

- reaching anything beyond login and public endpoints without authenticating, forging a session cookie,
  or using a device-grant or machine client-credentials token outside its allowed paths or scope;
- an authenticated user reading or changing another user's sessions, messages, files, artifacts, hosts,
  connections or stored credentials (IDOR), or exceeding a grant (read to edit, edit to manage, or
  bypassing `OMNIGENT_SHARING_MODE`);
- a host or sandbox tunnel acting for another user, binding to a session it does not own, or reusing a
  token beyond its scope;
- one user's input running as script in another user's web UI session (stored XSS). In the Electron app,
  treat XSS that reaches Node, IPC or the agent browser as code execution on the desktop;
- untrusted agent-visible content (prompt injection, a malicious repository, an MCP response) defeating a
  control Omnigent enforces: a DENY policy, an ASK approval that gets skipped or auto-approved, the
  `linux_bwrap` / `darwin_seatbelt` sandbox, or the browser URL policy;
- server-side path traversal, archive extraction outside its target (`omnigent/spec/tar_utils.py`,
  `omnigent/tools/builtins/upload_file.py`, agent bundles), or SSRF from the server to internal addresses;
- credentials (KMS-encrypted connections, the sandbox credential proxy, OAuth tokens) appearing in
  plaintext in logs, debug logs, API responses or the UI, or reaching a user they do not belong to.

## Components that matter most / least

Most:

- `omnigent/server/auth.py`, `oidc.py`, `oidc_access.py`, `accounts_*.py`, `device_grant_store.py`,
  `routes/auth.py`: authentication, cookies, device grant, client credentials.
- `omnigent/server/routes/` and `omnigent/stores/`: the permission check on every session, host, file and
  connection route; `routes/sessions/routes_permissions.py` for sharing.
- `omnigent/server/routes/host_tunnel.py`, `runner_tunnel.py`, `omnigent/server/host_registry.py`,
  `managed_hosts.py`: host and runner identity.
- `omnigent/server/mcp_gateway.py`, `mcp_*.py`, `connections_registry.py`: the MCP gateway and stored
  credentials.
- `omnigent/policies/`, `omnigent/runtime/policies/`, `omnigent/inner/sandbox.py`: policy evaluation and
  sandboxing.
- `web/src/` (rendering of messages, markdown, files and tool output; see
  `web/src/components/ai-elements/streamdown-security.ts`) and `web/electron/` (main process, IPC, the agent
  browser).

Least: `dev/` (developer tooling, including the Rust `omnidev`), `examples/`, `tests/`, `scripts/`,
`designs/`, `docs/`, `feature-map/`, `editors/`, `deploy/` (sample deployment manifests), and `.github/`.

## How to exercise it

The image has the full Python test environment in `/src/.venv` (on `PATH`) and the web UI built into
`omnigent/server/static/web-ui`. There is no network, so use the mock-LLM tests rather than real models.

- `omnigent server --help`; run a multi-user server locally with
  `OMNIGENT_AUTH_ENABLED=1 omnigent server --host 127.0.0.1 --admin-password <pw>` and log in through
  `/auth/login`.
- Auth and permission tests: `tests/server/test_auth_mode.py`, `test_permissions.py`,
  `test_public_sharing_policy.py`, `test_oidc_access.py`, `test_device_auth.py`.
- Server integration tests against a mock LLM: `tests/server/integration/` (for example
  `test_accounts_auth_e2e.py`, `test_host_tunnel_route.py`, `test_host_session_binding.py`,
  `test_hosts_filesystem.py`).
- Policies: `tests/policies/`. Sandbox: `tests/sandbox/` (bubblewrap needs unprivileged user namespaces).
- Run tests with `pytest <path> -m "not databricks"`. Web unit tests: `pnpm --filter web test`.

## How you rate severity

- **Critical**: unauthenticated code execution on the server; unauthenticated access to any user's sessions
  or credentials in a multi-user mode; one user running code on another user's host; XSS in the Electron
  app that reaches code execution.
- **High**: an authenticated user reading or changing another user's sessions, files, hosts or
  credentials; escalating a grant; host or tunnel impersonation; stored XSS that runs in another user's
  web session; untrusted content bypassing a DENY policy, an ASK approval or the sandbox; server-side path
  traversal that writes files.
- **Medium**: cross-user disclosure of metadata only (session titles, emails, host names); SSRF with no
  response returned; secrets written to server logs that only the operator can read; read-only path
  traversal limited to the server's own data directory.
- **Low**: denial of service by an authenticated user, missing hardening headers, and issues reachable
  only from a trusted role.

## Anything to leave alone

- The single-user local mode is unauthenticated by design. A server bound to a non-loopback interface with
  `OMNIGENT_LOCAL_SINGLE_USER=1` prints a warning; that configuration is the operator's choice.
- `header` auth trusts the identity header, and the operator must put an authenticating proxy in front of
  it. Spoofing the header against a server reached directly is not a vulnerability.
- Agents running commands, reading files or using the network on their own host is the product. It is a
  finding only when a sandbox or policy that was configured to stop it fails.
- Edit access to a session means driving its agent, which runs on the owner's host.
- Named-group grants (for example `team.engineering`) are free-text principals that are not resolved
  server-side. This is by design.
- Admins and the server operator seeing every session, and anything that requires control of server
  config, `policy_modules` or the deployment environment.
- Prompt injection on its own, when the agent only does what its configured permissions already allow.
- Dependency CVEs that are not reachable from Omnigent code; Trivy and Dependabot track these
  (`SECURITY.md`).
