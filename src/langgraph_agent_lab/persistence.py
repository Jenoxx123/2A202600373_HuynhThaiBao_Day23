"""Checkpointer adapter."""

from __future__ import annotations

import sqlite3


def _resolve_context_manager(maybe_cm: object) -> object:
    """Return a usable object for APIs that may return a context manager."""
    if hasattr(maybe_cm, "__enter__") and hasattr(maybe_cm, "__exit__"):
        saver = maybe_cm.__enter__()
        # Keep the manager alive so its __exit__ doesn't run and close the connection.
        saver._managed_cm = maybe_cm
        return saver
    return maybe_cm


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> object | None:
    """Return a LangGraph checkpointer implementation."""
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    if kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite"
            ) from exc
        conn = sqlite3.connect(database_url or "checkpoints.db")
        conn.execute("PRAGMA journal_mode=WAL;")
        return SqliteSaver(conn=conn)
    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpointer import failed. Ensure both "
                "'langgraph-checkpoint-postgres' and a psycopg backend are available. "
                "On Windows, install `psycopg-binary` (or system libpq) if you see "
                "'no pq wrapper available'. "
                f"Original error: {exc}"
            ) from exc
        if not database_url:
            raise RuntimeError("Postgres checkpointer requires a non-empty database_url")
        saver = _resolve_context_manager(PostgresSaver.from_conn_string(database_url))
        setup = getattr(saver, "setup", None)
        if callable(setup):
            setup()
        return saver
    raise ValueError(f"Unknown checkpointer kind: {kind}")
