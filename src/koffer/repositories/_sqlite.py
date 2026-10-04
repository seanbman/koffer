"""Shared SQLite helpers for typed repositories (no Qt types)."""

from __future__ import annotations

import sqlite3
from typing import Any

from koffer.domain.ids import EntityId


def as_entity_id(value: object) -> EntityId:
    return EntityId(str(value))


def as_optional_entity_id(value: object | None) -> EntityId | None:
    if value is None:
        return None
    return EntityId(str(value))


def bool_to_int(value: bool) -> int:
    return 1 if value else 0


def int_to_bool(value: int | bool) -> bool:
    return bool(int(value))


def optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_int(value: int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def row_count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    cursor = conn.execute(sql, params)
    return int(cursor.rowcount)
