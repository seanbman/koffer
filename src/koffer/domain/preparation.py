"""Preparation recipe and render plan value objects (docs/07, docs/19, docs/27)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from koffer.domain.enums import ConflictAction
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId

RECIPE_VERSION = 1

ChannelMode = Literal["source", "mono", "stereo"]
SourceOrInt = int | Literal["source"]
OutputFormat = Literal["wav", "flac", "ogg", "mp3"]
_CHANNEL_MODES = frozenset({"source", "mono", "stereo"})
_OUTPUT_FORMATS = frozenset({"wav", "flac", "ogg", "mp3"})


@dataclass(frozen=True, slots=True)
class TrimSpec:
    """Non-destructive trim window in milliseconds; end_ms None means file end."""

    start_ms: int = 0
    end_ms: int | None = None

    def validate(self) -> None:
        if self.start_ms < 0:
            raise ValidationError("trim.start_ms must be >= 0")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValidationError("trim.end_ms must be >= 0 when set")
        if self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValidationError("trim.end_ms must be >= trim.start_ms")


@dataclass(frozen=True, slots=True)
class NormalizeSpec:
    """Peak normalization request; never mutates source audio by itself."""

    enabled: bool = False
    target_peak_dbfs: float = -1.0


@dataclass(frozen=True, slots=True)
class PreparationRecipe:
    """Canonical preparation recipe JSON v1 (docs/19). Non-destructive until render."""

    version: int = RECIPE_VERSION
    trim: TrimSpec = field(default_factory=TrimSpec)
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    gain_db: float = 0.0
    normalize: NormalizeSpec = field(default_factory=NormalizeSpec)
    transpose_semitones: float = 0.0
    fine_cents: int = 0
    time_stretch_ratio: float = 1.0
    reverse: bool = False
    channels: ChannelMode = "source"
    sample_rate_hz: SourceOrInt = "source"
    bit_depth: SourceOrInt = "source"
    output_format: OutputFormat = "wav"

    @classmethod
    def default(cls) -> PreparationRecipe:
        return cls()

    def validate(self) -> None:
        if self.version != RECIPE_VERSION:
            raise ValidationError(f"unsupported recipe version: {self.version}")
        self.trim.validate()
        if self.fade_in_ms < 0 or self.fade_out_ms < 0:
            raise ValidationError("fade durations must be >= 0")
        if self.time_stretch_ratio <= 0:
            raise ValidationError("time_stretch_ratio must be > 0")
        if self.channels not in _CHANNEL_MODES:
            raise ValidationError(f"invalid channels mode: {self.channels}")
        if self.output_format not in _OUTPUT_FORMATS:
            raise ValidationError(f"invalid output_format: {self.output_format}")
        if self.sample_rate_hz != "source" and (
            not isinstance(self.sample_rate_hz, int) or self.sample_rate_hz <= 0
        ):
            raise ValidationError("sample_rate_hz must be 'source' or a positive int")
        if self.bit_depth != "source" and self.bit_depth not in {16, 24, 32}:
            raise ValidationError("bit_depth must be 'source', 16, 24, or 32")

    def to_json(self) -> dict[str, Any]:
        self.validate()
        return {
            "version": self.version,
            "trim": {"start_ms": self.trim.start_ms, "end_ms": self.trim.end_ms},
            "fade_in_ms": self.fade_in_ms,
            "fade_out_ms": self.fade_out_ms,
            "gain_db": self.gain_db,
            "normalize": {
                "enabled": self.normalize.enabled,
                "target_peak_dbfs": self.normalize.target_peak_dbfs,
            },
            "transpose_semitones": self.transpose_semitones,
            "fine_cents": self.fine_cents,
            "time_stretch_ratio": self.time_stretch_ratio,
            "reverse": self.reverse,
            "channels": self.channels,
            "sample_rate_hz": self.sample_rate_hz,
            "bit_depth": self.bit_depth,
            "output_format": self.output_format,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> PreparationRecipe:
        if not isinstance(data, dict):
            raise ValidationError("recipe JSON must be an object")
        version = int(data.get("version", RECIPE_VERSION))
        trim_raw = data.get("trim") or {}
        if not isinstance(trim_raw, dict):
            raise ValidationError("trim must be an object")
        end_raw = trim_raw.get("end_ms")
        end_ms = None if end_raw is None else int(end_raw)
        normalize_raw = data.get("normalize") or {}
        if not isinstance(normalize_raw, dict):
            raise ValidationError("normalize must be an object")
        sample_rate = data.get("sample_rate_hz", "source")
        if sample_rate != "source":
            sample_rate = int(sample_rate)
        bit_depth = data.get("bit_depth", "source")
        if bit_depth != "source":
            bit_depth = int(bit_depth)
        channels = str(data.get("channels", "source"))
        if channels not in _CHANNEL_MODES:
            raise ValidationError(f"invalid channels mode: {channels}")
        output_format = str(data.get("output_format", "wav"))
        if output_format not in _OUTPUT_FORMATS:
            raise ValidationError(f"invalid output_format: {output_format}")
        recipe = cls(
            version=version,
            trim=TrimSpec(
                start_ms=int(trim_raw.get("start_ms", 0)),
                end_ms=end_ms,
            ),
            fade_in_ms=int(data.get("fade_in_ms", 0)),
            fade_out_ms=int(data.get("fade_out_ms", 0)),
            gain_db=float(data.get("gain_db", 0.0)),
            normalize=NormalizeSpec(
                enabled=bool(normalize_raw.get("enabled", False)),
                target_peak_dbfs=float(normalize_raw.get("target_peak_dbfs", -1.0)),
            ),
            transpose_semitones=float(data.get("transpose_semitones", 0.0)),
            fine_cents=int(data.get("fine_cents", 0)),
            time_stretch_ratio=float(data.get("time_stretch_ratio", 1.0)),
            reverse=bool(data.get("reverse", False)),
            channels=cast(ChannelMode, channels),
            sample_rate_hz=cast(SourceOrInt, sample_rate),
            bit_depth=cast(SourceOrInt, bit_depth),
            output_format=cast(OutputFormat, output_format),
        )
        recipe.validate()
        return recipe

    def summary_lines(self) -> tuple[str, ...]:
        """Human-readable recipe summary for S08/S14."""
        lines = [
            f"trim: {self.trim.start_ms} ms → "
            f"{'end' if self.trim.end_ms is None else f'{self.trim.end_ms} ms'}",
            f"fade in/out: {self.fade_in_ms}/{self.fade_out_ms} ms",
            f"gain: {self.gain_db:+.1f} dB",
            f"normalize: {'on' if self.normalize.enabled else 'off'}"
            + (f" ({self.normalize.target_peak_dbfs:.1f} dBFS)" if self.normalize.enabled else ""),
            f"transpose: {self.transpose_semitones:+.1f} st / {self.fine_cents:+d} c",
            f"time stretch: {self.time_stretch_ratio:.3f}×",
            f"reverse: {'yes' if self.reverse else 'no'}",
            f"channels: {self.channels}",
            f"sample rate: {self.sample_rate_hz}",
            f"bit depth: {self.bit_depth}",
            f"output format: {self.output_format}",
        ]
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class PreviewHandle:
    """Preview descriptor; foundations mark quality without mutating source."""

    sample_id: EntityId
    recipe: PreparationRecipe
    quality: Literal["exact", "approximate"] = "approximate"
    note: str = "Preview approximates recipe; final render uses authoritative FFmpeg graph."


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Caller options for plan_render (docs/12 S14, docs/27)."""

    destination_dir: str
    filename: str
    conflict_policy: ConflictAction = ConflictAction.KEEP_BOTH
    carry_metadata: bool = True
    carry_artwork: bool = False
    collection_id: EntityId | None = None


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """Reviewed render plan; execute never writes into the source path."""

    id: str
    sample_id: EntityId
    source_path: str
    source_content_hash: str
    source_fingerprint: str
    destination_path: str
    recipe: PreparationRecipe
    conflict_policy: ConflictAction
    carry_metadata: bool
    carry_artwork: bool
    created_at: str
    collection_id: EntityId | None = None
    ffmpeg_argv: tuple[str, ...] = ()

    def to_scope(self) -> dict[str, object]:
        return {
            "plan_id": self.id,
            "sample_id": str(self.sample_id),
            "source_path": self.source_path,
            "source_content_hash": self.source_content_hash,
            "source_fingerprint": self.source_fingerprint,
            "destination_path": self.destination_path,
            "recipe": self.recipe.to_json(),
            "conflict_policy": str(self.conflict_policy),
            "carry_metadata": self.carry_metadata,
            "carry_artwork": self.carry_artwork,
            "created_at": self.created_at,
            "collection_id": str(self.collection_id) if self.collection_id else None,
            "ffmpeg_argv": list(self.ffmpeg_argv),
        }

    @classmethod
    def from_scope(cls, scope: dict[str, Any]) -> RenderPlan:
        recipe = PreparationRecipe.from_json(dict(scope["recipe"]))
        collection_raw = scope.get("collection_id")
        argv_raw = scope.get("ffmpeg_argv") or []
        if not isinstance(argv_raw, list):
            raise ValidationError("ffmpeg_argv must be a list")
        return cls(
            id=str(scope["plan_id"]),
            sample_id=EntityId(str(scope["sample_id"])),
            source_path=str(scope["source_path"]),
            source_content_hash=str(scope["source_content_hash"]),
            source_fingerprint=str(scope["source_fingerprint"]),
            destination_path=str(scope["destination_path"]),
            recipe=recipe,
            conflict_policy=ConflictAction(str(scope["conflict_policy"])),
            carry_metadata=bool(scope.get("carry_metadata", True)),
            carry_artwork=bool(scope.get("carry_artwork", False)),
            created_at=str(scope["created_at"]),
            collection_id=EntityId(str(collection_raw)) if collection_raw else None,
            ffmpeg_argv=tuple(str(part) for part in argv_raw),
        )
