# Session sharing

Session access requires a user identity on a multi-user server. Public access
does not bypass authentication: a `__public__` grant lets anyone who can sign in
and has the link access a session without an individual invitation.
The server's authentication boundary defines the audience, including built-in
accounts, OIDC, and trusted-header SSO deployments.
Configured client-credential machine principals are also part of this audience.

Admins choose **Settings > Sharing > Maximum public permission**. The default
is **Read**; **Edit** is available only with authenticated multi-user access.
The setting can also be changed with:

```http
PUT /v1/sharing
Content-Type: application/json

{"public_sharing_max_level": "edit"}
```

This permits public Edit grants, but does not upgrade existing Read grants.
Owners and managers choose **Share > General access > No access / Read / Edit**,
or grant access through the permissions API:

```http
PUT /v1/sessions/{id}/permissions
Content-Type: application/json

{"user_id": "__public__", "level": 2}
```

Edit lets collaborators send follow-ups and use the session's shared workspace.
Public grants cannot confer Manage or Owner, even if a stored grant contains a
higher level. Direct Manage/Owner grants remain effective; public Edit elevates
an individual Read grant. Future signed-in users receive the same link access.
Public-only sessions do not automatically appear in everyone's sidebar.

Lowering the ceiling to Read immediately limits existing public Edit grants,
including cached access and ongoing streams. The stored grants are not changed:
raising the ceiling again restores their Edit access. Invalid configuration and
servers without authenticated multi-user access fall back to Read.

`sharing_mode` and `public_sharing` continue to gate new grants. Existing grants
remain readable and revocable after those policies change; the public permission
ceiling applies during authorization as well. Default-public session creation
still grants Read, even when Edit is permitted.

The file-backed setting defaults from `OMNIGENT_PUBLIC_SHARING_MAX_LEVEL`
(`read` / `edit`) and persists to `<data_dir>/public_sharing_max_level`.
Deployments can inject a static value or a callable through
`create_app(public_sharing_max_level=...)`; such settings are not admin-editable.
`GET /v1/info` advertises the effective ceiling. Clients treat older servers or
missing/invalid capability values as Read-only.

Agents need `agent_session_sharing: public` to use `sys_session_share` with
`user_id: "__public__"` and `level: "edit"`. The server enforces the same limits
as the UI; the `non-public` policy permits named-user grants only.
