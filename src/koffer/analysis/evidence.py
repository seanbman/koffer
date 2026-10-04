"""Versioned Suggestion evidence helpers (docs/06, docs/19)."""

from __future__ import annotations

import json
from typing import Any

EVIDENCE_SCHEMA_VERSION = 1


def build_evidence(**channels: Any) -> str:
    """Serialize a multi-channel evidence object as JSON text for suggestions.evidence_json."""
    payload: dict[str, Any] = {"version": EVIDENCE_SCHEMA_VERSION}
    for key, value in channels.items():
        if value is not None:
            payload[key] = value
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def parse_evidence(evidence_json: str) -> dict[str, Any]:
    """Best-effort parse of stored evidence JSON."""
    try:
        raw = json.loads(evidence_json)
    except json.JSONDecodeError:
        return {"version": EVIDENCE_SCHEMA_VERSION, "raw": evidence_json}
    if isinstance(raw, dict):
        return raw
    return {"version": EVIDENCE_SCHEMA_VERSION, "value": raw}
