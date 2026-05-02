from __future__ import annotations
"""PostgreSQL persistence for auth users (register / login).

Table: ``code4u_auth_users`` (created automatically on first use).
DSN must be a ``postgresql://`` URL (``postgresql+asyncpg://`` is normalized).
"""
import threading
from datetime import datetime
from typing import Optional

import structlog

logger = structlog.get_logger("auth.postgres_store")

try:
    import psycopg
except ImportError:  # pragma: no cover - guarded at runtime in AuthManager
    psycopg = None  # type: ignore[misc, assignment]


def sync_postgresql_dsn(url: str) -> str:
    """Strip SQLAlchemy/async driver prefixes for psycopg."""
    u = (url or "").strip()
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres+asyncpg://"):
        if u.startswith(prefix):
            return "postgresql://" + u[len(prefix) :]
    return u


_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS code4u_auth_users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    tenant_id TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
"""

_SCHEMA_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_code4u_auth_users_email_lower
    ON code4u_auth_users (LOWER(email));
"""


class PostgresAuthStore:
    """Thread-safe sync access (FastAPI handlers await other I/O; auth stays sync)."""

    def __init__(self, dsn: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required for Postgres auth persistence")
        self._dsn = sync_postgresql_dsn(dsn)
        self._lock = threading.Lock()
        self._conn: Optional["psycopg.Connection"] = None
        self._schema_ready = False

    def _connect(self) -> "psycopg.Connection":
        assert psycopg is not None
        return psycopg.connect(self._dsn, autocommit=True)

    def _conn_live(self) -> "psycopg.Connection":
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = self._connect()
                self._schema_ready = False
            if not self._schema_ready:
                with self._conn.cursor() as cur:
                    cur.execute(_SCHEMA_TABLE)
                    cur.execute(_SCHEMA_INDEX)
                self._schema_ready = True
                logger.info("auth_postgres_schema_ready")
            return self._conn

    def email_exists(self, email: str) -> bool:
        key = email.strip().lower()
        conn = self._conn_live()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM code4u_auth_users WHERE LOWER(email) = %s LIMIT 1",
                (key,),
            )
            return cur.fetchone() is not None

    def insert_user(
        self,
        *,
        user_id: str,
        email: str,
        hashed_password: str,
        name: str,
        company: str,
        tenant_id: str,
    ) -> None:
        conn = self._conn_live()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO code4u_auth_users
                    (user_id, email, hashed_password, name, company, tenant_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, email.strip().lower(), hashed_password, name, company, tenant_id),
            )

    def fetch_by_email(self, email: str) -> Optional[tuple]:
        key = email.strip().lower()
        conn = self._conn_live()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, email, hashed_password, name, company, tenant_id,
                       created_at, is_active
                FROM code4u_auth_users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (key,),
            )
            return cur.fetchone()

    def fetch_by_id(self, user_id: str) -> Optional[tuple]:
        conn = self._conn_live()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, email, hashed_password, name, company, tenant_id,
                       created_at, is_active
                FROM code4u_auth_users
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone()
