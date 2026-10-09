# Session sharing

Owners and managers can grant session access with
`PUT /v1/sessions/{id}/permissions`. Named users may receive read (1),
edit (2), or manage (3). Owners retain their separate owner grant.

Two group grantees are supported:

- `__public__`: read-only access for anyone with the link, subject to the
  deployment's authentication requirements and `public_sharing` setting.
- `__authenticated__`: read or edit access for all signed-in users on this
  server. It does not match anonymous requests or the local single-user
  identity, and cannot grant manage or owner access.

For a shared company server, an automation can create a session and then grant
signed-in users edit access without enumerating accounts:

```http
PUT /v1/sessions/{id}/permissions
Content-Type: application/json

{"user_id": "__authenticated__", "level": 2}
```

The requester must be authenticated and already have manage access. Future
users receive the same access when they sign in. The server's authentication
boundary defines the group: this is not an email-domain filter. Only enable
the grant on a server whose allowed sign-ins match the intended audience.
Edit access lets collaborators send follow-ups and use the session's shared
workspace; it does not authorize permission management or owner-only actions.

The Share dialog offers **All signed-in users** with **No access**, **Read**,
and **Edit**. Choosing **No access** revokes the group grant. The
`authenticated_sharing_enabled` capability on `/v1/info` advertises support;
older servers omit it and the control stays hidden.
The agent sharing tool also requires this capability to be explicitly true
before sending a signed-in-user grant.

When upgrading, a legacy individual identity or orphaned permission named
`__authenticated__` is not converted into a group. Such grants remain inactive,
and new group grants return a conflict until an operator resolves the legacy
identity and its grants. The store marks only a newly created group principal
using its existing account-generation field; no schema migration is required.

`sharing_mode` applies to both named and group grants. Read-only modes reject
new edit grants, restricted read-only also blocks sharing home/root workspaces,
and off rejects all new grants. The `public_sharing` switch applies only to
`__public__`. Existing grants remain usable and revocable after a policy change.

A signed-in-user grant raises a user's effective level to at least the group
level, even if they have an individual read grant. Individual manage/owner
grants remain effective. Child sessions inherit access from their parent.
Group-only sessions are reached by link, not automatically listed in every
user's sidebar. Revoking an individual grant does not remove group access.

Agents with `agent_session_sharing: non-public` or `public` can use
`sys_session_share` with `user_id: "__authenticated__"` and `level: "edit"`.
The server enforces the same authorization and policy limits as the UI/API.
