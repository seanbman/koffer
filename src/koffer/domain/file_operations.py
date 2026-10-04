"""File operation plan value objects (docs/03, docs/27)."""

from __future__ import annotations

from dataclasses import dataclass

from koffer.domain.enums import ConflictAction, FileOperationKind
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId


@dataclass(frozen=True, slots=True)
class ConflictPolicy:
    """Batch conflict default; Review never silently overwrites (docs/28)."""

    default_action: ConflictAction = ConflictAction.REVIEW


@dataclass(frozen=True, slots=True)
class PlannedFileItem:
    """One Sample in a reviewed file-operation plan."""

    sample_id: EntityId
    source_path: str
    source_fingerprint: str
    destination_path: str | None
    conflict: bool
    conflict_action: ConflictAction
    destination_exists: bool
    note: str | None = None


@dataclass(frozen=True, slots=True)
class FileOperationPlan:
    """Reviewed plan; execute refuses unresolved Review conflicts and stale fingerprints."""

    id: str
    kind: FileOperationKind
    items: tuple[PlannedFileItem, ...]
    destination_root: str | None
    conflict_policy: ConflictPolicy
    created_at: str

    def unresolved_conflicts(self) -> tuple[PlannedFileItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.conflict and item.conflict_action is ConflictAction.REVIEW
        )

    def to_scope(self) -> dict[str, object]:
        return {
            "plan_id": self.id,
            "kind": str(self.kind),
            "destination_root": self.destination_root,
            "conflict_policy": str(self.conflict_policy.default_action),
            "created_at": self.created_at,
            "items": [
                {
                    "sample_id": str(item.sample_id),
                    "source_path": item.source_path,
                    "source_fingerprint": item.source_fingerprint,
                    "destination_path": item.destination_path,
                    "conflict": item.conflict,
                    "conflict_action": str(item.conflict_action),
                    "destination_exists": item.destination_exists,
                    "note": item.note,
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_scope(cls, scope: dict[str, object]) -> FileOperationPlan:
        raw_items = scope.get("items")
        if not isinstance(raw_items, list):
            msg = "plan scope missing items"
            raise ValidationError(msg)
        items: list[PlannedFileItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            dest = raw.get("destination_path")
            note = raw.get("note")
            items.append(
                PlannedFileItem(
                    sample_id=EntityId(str(raw["sample_id"])),
                    source_path=str(raw["source_path"]),
                    source_fingerprint=str(raw["source_fingerprint"]),
                    destination_path=None if dest is None else str(dest),
                    conflict=bool(raw.get("conflict", False)),
                    conflict_action=ConflictAction(str(raw["conflict_action"])),
                    destination_exists=bool(raw.get("destination_exists", False)),
                    note=None if note is None else str(note),
                )
            )
        policy_raw = scope.get("conflict_policy", ConflictAction.REVIEW)
        dest_root = scope.get("destination_root")
        return cls(
            id=str(scope.get("plan_id", "")),
            kind=FileOperationKind(str(scope["kind"])),
            items=tuple(items),
            destination_root=None if dest_root is None else str(dest_root),
            conflict_policy=ConflictPolicy(default_action=ConflictAction(str(policy_raw))),
            created_at=str(scope.get("created_at", "")),
        )
