"""Timestamp helpers for domain and persistence layers.

Convention (locked in migration 001): UTC ISO-8601 text with explicit offset,
e.g. ``2026-10-04T20:25:47.511374+00:00``. Never mix with Unix microseconds.
"""

from __future__ import annotations

from datetime import UTC, datetime

TIMESTAMP_CONVENTION = "utc_iso8601_text"


def utc_now_iso() -> str:
    """Current UTC time as ISO-8601 text with ``+00:00`` offset."""
    return datetime.now(UTC).isoformat()
