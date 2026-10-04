"""Application-generated durable identity helpers."""

from __future__ import annotations

import uuid
from typing import NewType

EntityId = NewType("EntityId", str)


def new_entity_id() -> EntityId:
    """Return a new UUIDv4 text ID for durable domain entities."""
    return EntityId(str(uuid.uuid4()))
