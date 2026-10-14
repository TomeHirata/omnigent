"""Migration ``nn1a2b3c4d5e`` adds bounded, nullable credential epochs.

Existing users and credentials must upgrade with a ``NULL`` epoch (never
rotated) and otherwise unchanged. Every ``credential_epoch`` must reject values
over 32 characters even on SQLite, which ignores ``VARCHAR`` lengths, in both
migrated and ORM-created schemas. An interrupted upgrade must resume, and the
downgrade must drop the columns while keeping the rows.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command

from omnigent.db.db_models import OmnigentBase
from omnigent.db.utils import _build_alembic_config, clear_engine_cache

_TABLES = ("users", "account_tokens", "device_grants")
_ROW_IDS = {"users": "alice", "account_tokens": "magic", "device_grants": "grant"}
_PREVIOUS = "mm1a2b3c4d5e"
# The first value size the database guide prohibits for a column.
_PROHIBITED = "a" * 16_384


def _columns(connection: sa.Connection, table: str) -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(connection).get_columns(table)}


def _insert_credentials(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO users (id, is_admin, password_hash, account_generation) "
            "VALUES ('alice', 0, 'hash', 'generation')"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO account_tokens (id, kind, user_id, created_at, expires_at, "
            "invited_is_admin, account_generation) VALUES ('magic', 2, 'alice', 1, 2, "
            "0, 'generation')"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO device_grants (id, device_code_hash, user_code, status, "
            "user_id, created_at, expires_at, refresh_token_hash, account_generation) "
            "VALUES ('grant', 'device', 'code', 4, 'alice', 1, 2, 'refresh', "
            "'generation')"
        )
    )


def _set_epoch(engine: sa.Engine, table: str, epoch: str | None) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(f"UPDATE {table} SET credential_epoch = :epoch WHERE id = :id"),
            {"epoch": epoch, "id": _ROW_IDS[table]},
        )


def _assert_epoch_bounded(engine: sa.Engine) -> None:
    for table in _TABLES:
        for oversized in ("a" * 33, _PROHIBITED):
            with pytest.raises(sa.exc.IntegrityError, match=f"ck_{table}_credential_epoch"):
                _set_epoch(engine, table, oversized)
        for accepted in (uuid.uuid4().hex, None):
            _set_epoch(engine, table, accepted)


def test_upgrade_keeps_existing_credentials_and_downgrade_drops_columns(tmp_path: Path) -> None:
    uri = f"sqlite:///{tmp_path / 'credential-epoch.db'}"
    config = _build_alembic_config(uri)
    engine = sa.create_engine(uri)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, _PREVIOUS)
            _insert_credentials(connection)
            command.upgrade(config, "head")
            for table in _TABLES:
                column = _columns(connection, table)["credential_epoch"]
                assert column["nullable"] is True
                assert column["type"].length == 32
                row = connection.execute(
                    sa.text(
                        f"SELECT account_generation, credential_epoch FROM {table} WHERE id = :id"
                    ),
                    {"id": _ROW_IDS[table]},
                ).one()
                assert row == ("generation", None)

        _assert_epoch_bounded(engine)

        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, _PREVIOUS)
            for table in _TABLES:
                assert "credential_epoch" not in _columns(connection, table)
                kept = connection.execute(
                    sa.text(f"SELECT account_generation FROM {table} WHERE id = :id"),
                    {"id": _ROW_IDS[table]},
                ).scalar_one()
                assert kept == "generation"
    finally:
        engine.dispose()
        clear_engine_cache()


def test_orm_created_schema_enforces_the_same_bound(tmp_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'credential-epoch-orm.db'}")
    try:
        OmnigentBase.metadata.create_all(engine)
        with engine.begin() as connection:
            _insert_credentials(connection)
        _assert_epoch_bounded(engine)
    finally:
        engine.dispose()


def test_upgrade_resumes_after_a_partially_applied_revision(tmp_path: Path) -> None:
    uri = f"sqlite:///{tmp_path / 'credential-epoch-resume.db'}"
    config = _build_alembic_config(uri)
    engine = sa.create_engine(uri)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, _PREVIOUS)
            _insert_credentials(connection)
            # Engines that commit DDL per statement can stop after the first table.
            connection.execute(
                sa.text(
                    "ALTER TABLE users ADD COLUMN credential_epoch VARCHAR(32) CONSTRAINT "
                    "ck_users_credential_epoch CHECK (length(credential_epoch) <= 32)"
                )
            )
            command.upgrade(config, "head")
            for table in _TABLES:
                assert "credential_epoch" in _columns(connection, table)
        _assert_epoch_bounded(engine)
    finally:
        engine.dispose()
        clear_engine_cache()
