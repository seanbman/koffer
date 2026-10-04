"""Metadata write plan value objects (docs/05, docs/19, docs/27)."""

from __future__ import annotations

from dataclasses import dataclass

from koffer.domain.enums import ArtworkAction, MetadataWriteTarget
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId


@dataclass(frozen=True, slots=True)
class ArtworkPayload:
    """Raw embedded artwork bytes with MIME type."""

    data: bytes
    mime: str = "image/jpeg"


@dataclass(frozen=True, slots=True)
class MetadataWriteRequest:
    """Caller request for plan_write (docs/27)."""

    sample_ids: tuple[EntityId, ...]
    target: MetadataWriteTarget
    fields: dict[str, str | None]
    artwork_action: ArtworkAction = ArtworkAction.KEEP
    artwork: ArtworkPayload | None = None
    copy_destination_dir: str | None = None


@dataclass(frozen=True, slots=True)
class MetadataWriteException:
    """Per-item/per-field blocker shown before execute (batch exception review)."""

    sample_id: EntityId
    field: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PlannedMetadataItem:
    """One Sample in a reviewed metadata write plan."""

    sample_id: EntityId
    source_path: str
    source_fingerprint: str
    source_content_hash: str
    destination_path: str
    format_id: str
    writable_fields: tuple[str, ...]
    artwork_support: bool
    note: str | None = None


@dataclass(frozen=True, slots=True)
class MetadataWritePlan:
    """Reviewed plan; execute refuses blocking exceptions and stale fingerprints."""

    id: str
    target: MetadataWriteTarget
    items: tuple[PlannedMetadataItem, ...]
    fields: dict[str, str | None]
    artwork_action: ArtworkAction
    artwork: ArtworkPayload | None
    exceptions: tuple[MetadataWriteException, ...]
    created_at: str
    copy_destination_dir: str | None = None

    def blocking_exceptions(self) -> tuple[MetadataWriteException, ...]:
        return self.exceptions

    def to_scope(self) -> dict[str, object]:
        artwork_b64: str | None = None
        artwork_mime: str | None = None
        if self.artwork is not None:
            import base64

            artwork_b64 = base64.b64encode(self.artwork.data).decode("ascii")
            artwork_mime = self.artwork.mime
        return {
            "plan_id": self.id,
            "target": str(self.target),
            "created_at": self.created_at,
            "copy_destination_dir": self.copy_destination_dir,
            "fields": dict(self.fields),
            "artwork_action": str(self.artwork_action),
            "artwork_b64": artwork_b64,
            "artwork_mime": artwork_mime,
            "exceptions": [
                {
                    "sample_id": str(exc.sample_id),
                    "field": exc.field,
                    "code": exc.code,
                    "message": exc.message,
                }
                for exc in self.exceptions
            ],
            "items": [
                {
                    "sample_id": str(item.sample_id),
                    "source_path": item.source_path,
                    "source_fingerprint": item.source_fingerprint,
                    "source_content_hash": item.source_content_hash,
                    "destination_path": item.destination_path,
                    "format_id": item.format_id,
                    "writable_fields": list(item.writable_fields),
                    "artwork_support": item.artwork_support,
                    "note": item.note,
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_scope(cls, scope: dict[str, object]) -> MetadataWritePlan:
        raw_items = scope.get("items")
        if not isinstance(raw_items, list):
            raise ValidationError("metadata write plan scope missing items")
        items: list[PlannedMetadataItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            writable = raw.get("writable_fields", ())
            if not isinstance(writable, list | tuple):
                writable = ()
            note = raw.get("note")
            items.append(
                PlannedMetadataItem(
                    sample_id=EntityId(str(raw["sample_id"])),
                    source_path=str(raw["source_path"]),
                    source_fingerprint=str(raw["source_fingerprint"]),
                    source_content_hash=str(raw["source_content_hash"]),
                    destination_path=str(raw["destination_path"]),
                    format_id=str(raw["format_id"]),
                    writable_fields=tuple(str(f) for f in writable),
                    artwork_support=bool(raw.get("artwork_support", False)),
                    note=None if note is None else str(note),
                )
            )
        raw_exceptions = scope.get("exceptions", [])
        exceptions: list[MetadataWriteException] = []
        if isinstance(raw_exceptions, list):
            for raw in raw_exceptions:
                if not isinstance(raw, dict):
                    continue
                exceptions.append(
                    MetadataWriteException(
                        sample_id=EntityId(str(raw["sample_id"])),
                        field=str(raw["field"]),
                        code=str(raw["code"]),
                        message=str(raw["message"]),
                    )
                )
        fields_raw = scope.get("fields", {})
        fields: dict[str, str | None] = {}
        if isinstance(fields_raw, dict):
            for key, value in fields_raw.items():
                fields[str(key)] = None if value is None else str(value)
        artwork: ArtworkPayload | None = None
        artwork_b64 = scope.get("artwork_b64")
        if isinstance(artwork_b64, str) and artwork_b64:
            import base64

            mime = scope.get("artwork_mime")
            artwork = ArtworkPayload(
                data=base64.b64decode(artwork_b64.encode("ascii")),
                mime=str(mime) if isinstance(mime, str) and mime else "image/jpeg",
            )
        copy_dir = scope.get("copy_destination_dir")
        return cls(
            id=str(scope.get("plan_id", "")),
            target=MetadataWriteTarget(str(scope["target"])),
            items=tuple(items),
            fields=fields,
            artwork_action=ArtworkAction(str(scope.get("artwork_action", ArtworkAction.KEEP))),
            artwork=artwork,
            exceptions=tuple(exceptions),
            created_at=str(scope.get("created_at", "")),
            copy_destination_dir=None if copy_dir is None else str(copy_dir),
        )


@dataclass(frozen=True, slots=True)
class MetadataEditFieldState:
    """One editor field with capability-aware enablement."""

    name: str
    value: str | None
    writable: bool
    mixed: bool
    explanation: str | None = None


@dataclass(frozen=True, slots=True)
class MetadataEditState:
    """S09 editor model: embeddable vs Koffer-only, with capability explanations."""

    sample_ids: tuple[EntityId, ...]
    format_ids: tuple[str, ...]
    embeddable_fields: tuple[MetadataEditFieldState, ...]
    artwork_supported: bool
    artwork_present: bool
    artwork_explanation: str | None
    koffer_tags: tuple[str, ...]
    limitations: tuple[str, ...]
