"""add credential epochs to accounts users and credentials

Revision ID: nn1a2b3c4d5e
Revises: mm1a2b3c4d5e
Create Date: 2026-10-14 00:00:00.000000

Adds a nullable ``credential_epoch`` (32-character hex) to ``users``,
``account_tokens`` and ``device_grants``. A user's epoch names the current
set of sign-in credentials, separately from ``account_generation``, which
identifies the registration that owns hosts and scheduled tasks. Rotating it
is a single-row update of ``users``; no owned rows change.

``NULL`` means the epoch has never been rotated, so existing rows need no
backfill and every credential issued before this revision stays valid. A
named CHECK bounds each value to 32 characters; SQLite does not enforce the
declared ``VARCHAR`` length.

Deployment: additive and nullable. Releases that include this revision map
the columns in whole-row reads and inserts, so the database must be at this
revision before they serve requests. Server startup applies it automatically;
deployments that apply schema separately must apply it first. Instances of
the previous release that are already running ignore the columns, so a
rolling deploy is safe, but the previous release refuses to start against
this revision. To roll back, stop every instance of the newer release,
downgrade to ``mm1a2b3c4d5e`` with the newer release's migrations, then start
the previous release. Downgrading drops the columns and any rotation state.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "nn1a2b3c4d5e"
down_revision: str | None = "mm1a2b3c4d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "credential_epoch"
_TABLES = ("users", "account_tokens", "device_grants")


def _constraint(table: str) -> str:
    return f"ck_{table}_{_COLUMN}"


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        # MySQL and CockroachDB commit DDL per statement; skip columns a
        # previously interrupted upgrade already added.
        if _COLUMN in {column["name"] for column in sa.inspect(bind).get_columns(table)}:
            continue
        # One ADD COLUMN carries the bound, so a column never exists without it.
        op.add_column(
            table,
            sa.Column(
                _COLUMN,
                sa.String(32),
                sa.CheckConstraint(f"length({_COLUMN}) <= 32", name=_constraint(table)),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(_constraint(table), type_="check")
            batch_op.drop_column(_COLUMN)
