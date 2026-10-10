"""Local AI setup, status, and library backfill (docs/32, S18).

Surface stays plain-language: model download is not user-audio upload.
Suggestions remain pending until the user accepts or edits them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from koffer.analysis.manifest import (
    ModelManifest,
    check_model_manifest,
    load_model_manifest,
    resolve_model_artifact_path,
)
from koffer.analysis.model_install import (
    CancelCheck,
    InstallProgress,
    ProgressCallback,
    install_model_artifact,
)
from koffer.analysis.panns import PannsSemanticProvider
from koffer.domain.enums import AnalysisDepth, JobType, SampleAvailability
from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import path_fingerprint
from koffer.jobs.scheduler import JobSpec
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.services.settings import SettingsService

if TYPE_CHECKING:
    from koffer.analysis.embeddings import EmbeddingStore
    from koffer.analysis.semantic import SemanticProvider
    from koffer.jobs.scheduler import JobScheduler
    from koffer.services.analysis import AnalysisService
    from koffer.services.similarity import SimilarityService

__all__ = [
    "BackfillPlan",
    "LocalAiService",
    "LocalAiStatus",
    "LocalAiStatusKind",
    "WorkloadSize",
    "discovery_analysis_depth",
    "format_byte_size",
]


class LocalAiStatusKind(StrEnum):
    """Coarse Local AI card states for Settings → Library & Analysis."""

    NOT_INSTALLED = "not_installed"
    MANIFEST_BLOCKED = "manifest_blocked"
    INSTALLED_DISABLED = "installed_disabled"
    ENABLED = "enabled"
    ERROR = "error"
    DOWNLOADING = "downloading"


class WorkloadSize(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass(frozen=True, slots=True)
class LocalAiStatus:
    """Human-readable Local AI card snapshot (no raw exception dumps)."""

    kind: LocalAiStatusKind
    headline: str
    detail: str
    privacy_note: str
    model_name: str
    model_version: str
    provider_label: str
    size_label: str
    install_ready: bool
    install_blocked_reason: str | None
    artifact_present: bool
    checksum_ok: bool | None
    enabled: bool
    automatic_analysis: bool
    can_enable: bool
    can_analyze_existing: bool
    can_rebuild: bool
    embedding_index_label: str


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    """Pre-flight summary before Analyze Existing Library queues work."""

    sample_ids: tuple[EntityId, ...]
    sample_count: int
    model_name: str
    model_version: str
    workload: WorkloadSize
    depth: AnalysisDepth


PRIVACY_NOTE = (
    "Runs on this computer. Installing the model downloads software to your machine; "
    "your audio is never uploaded for Local AI classification."
)


def format_byte_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "size pending"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"


def workload_for_count(count: int) -> WorkloadSize:
    if count < 100:
        return WorkloadSize.SMALL
    if count < 1000:
        return WorkloadSize.MEDIUM
    return WorkloadSize.LARGE


def discovery_analysis_depth(
    *,
    automatic_analysis: bool,
    local_model_enabled: bool,
    provider_available: bool,
) -> AnalysisDepth | None:
    """Decide post-discovery analysis depth.

    Returns ``None`` when automatic analysis is off (no queue). Otherwise
    returns FULL only when Local AI is enabled and the verified provider is ready.
    """
    if not automatic_analysis:
        return None
    if local_model_enabled and provider_available:
        return AnalysisDepth.FULL
    return AnalysisDepth.DETERMINISTIC


class LocalAiService:
    """Settings-facing Local AI operations: status, install, enable, backfill."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        settings_service: SettingsService,
        *,
        cache_dir: Path,
        scheduler: JobScheduler | None = None,
        analysis_service: AnalysisService | None = None,
        similarity_service: SimilarityService | None = None,
        semantic_provider: SemanticProvider | None = None,
        embedding_store: EmbeddingStore | None = None,
    ) -> None:
        self._factory = connection_factory
        self._settings = settings_service
        self._cache_dir = Path(cache_dir)
        self._scheduler = scheduler
        self._analysis = analysis_service
        self._similarity = similarity_service
        self._provider = semantic_provider
        self._embeddings = embedding_store
        self._download_active = False

    def status(self) -> LocalAiStatus:
        lib = self._settings.load().library_analysis
        try:
            manifest = self._active_manifest()
        except ValidationError as exc:
            return LocalAiStatus(
                kind=LocalAiStatusKind.ERROR,
                headline="Local AI model setup needs attention",
                detail="The model description file could not be read. Try again from Settings.",
                privacy_note=PRIVACY_NOTE,
                model_name="Local AI",
                model_version="unknown",
                provider_label="Local AI",
                size_label="unknown",
                install_ready=False,
                install_blocked_reason=exc.summary,
                artifact_present=False,
                checksum_ok=None,
                enabled=lib.local_model_enabled,
                automatic_analysis=lib.automatic_analysis,
                can_enable=False,
                can_analyze_existing=False,
                can_rebuild=False,
                embedding_index_label="Unavailable",
            )

        artifact_path = resolve_model_artifact_path(self._cache_dir, manifest)
        if isinstance(self._provider, PannsSemanticProvider):
            artifact_path = self._provider.artifact_path
        artifact_present = artifact_path.is_file()
        checksum_ok: bool | None = None
        if manifest.path is not None:
            check = check_model_manifest(
                manifest_path=manifest.path,
                cache_dir=self._cache_dir,
            )
            checksum_ok = check.checksum_ok
        if artifact_present and manifest.checksum_recorded:
            try:
                from koffer.analysis.manifest import verify_model_artifact

                verify_model_artifact(artifact_path, manifest)
                checksum_ok = True
            except ValidationError:
                checksum_ok = False
        size_label = format_byte_size(
            artifact_path.stat().st_size if artifact_present else manifest.size_bytes
        )
        provider_label = f"{manifest.provider.upper()} {manifest.model}"
        model_name = f"{manifest.model} ({manifest.provider})"
        embedding_label = self._embedding_index_label(manifest.model_version)

        if self._download_active:
            return LocalAiStatus(
                kind=LocalAiStatusKind.DOWNLOADING,
                headline="Downloading Local AI model…",
                detail="Checksum verification runs before the model becomes trusted.",
                privacy_note=PRIVACY_NOTE,
                model_name=model_name,
                model_version=manifest.version,
                provider_label=provider_label,
                size_label=size_label,
                install_ready=False,
                install_blocked_reason=None,
                artifact_present=artifact_present,
                checksum_ok=checksum_ok,
                enabled=lib.local_model_enabled,
                automatic_analysis=lib.automatic_analysis,
                can_enable=False,
                can_analyze_existing=False,
                can_rebuild=False,
                embedding_index_label=embedding_label,
            )

        if not manifest.checksum_recorded:
            return LocalAiStatus(
                kind=LocalAiStatusKind.MANIFEST_BLOCKED,
                headline="Local AI model not ready to install",
                detail=(
                    "The model checksum is not recorded yet, so Koffer will not download "
                    "or trust weights. Browsing and import still work without Local AI."
                ),
                privacy_note=PRIVACY_NOTE,
                model_name=model_name,
                model_version=manifest.version,
                provider_label=provider_label,
                size_label=size_label,
                install_ready=False,
                install_blocked_reason="Model checksum is not recorded in the manifest",
                artifact_present=artifact_present,
                checksum_ok=checksum_ok,
                enabled=False,
                automatic_analysis=lib.automatic_analysis,
                can_enable=False,
                can_analyze_existing=False,
                can_rebuild=False,
                embedding_index_label=embedding_label,
            )

        if artifact_present and checksum_ok is False:
            return LocalAiStatus(
                kind=LocalAiStatusKind.ERROR,
                headline="Local AI model failed verification",
                detail=(
                    "The installed file did not match the expected checksum. "
                    "Remove the bad file and install again. Your audio library is unchanged."
                ),
                privacy_note=PRIVACY_NOTE,
                model_name=model_name,
                model_version=manifest.version,
                provider_label=provider_label,
                size_label=size_label,
                install_ready=True,
                install_blocked_reason=None,
                artifact_present=True,
                checksum_ok=False,
                enabled=lib.local_model_enabled,
                automatic_analysis=lib.automatic_analysis,
                can_enable=False,
                can_analyze_existing=False,
                can_rebuild=False,
                embedding_index_label=embedding_label,
            )

        provider_ok = self._provider_available(enabled=True)
        if not artifact_present or not provider_ok:
            # Artifact may exist but torch missing — still treat as not fully installed.
            if not artifact_present:
                return LocalAiStatus(
                    kind=LocalAiStatusKind.NOT_INSTALLED,
                    headline="Local AI model not installed",
                    detail=(
                        "Install the on-device model so Koffer can suggest instruments, "
                        "roles, and similar sounds. Import and browsing work without it."
                    ),
                    privacy_note=PRIVACY_NOTE,
                    model_name=model_name,
                    model_version=manifest.version,
                    provider_label=provider_label,
                    size_label=size_label,
                    install_ready=True,
                    install_blocked_reason=None,
                    artifact_present=False,
                    checksum_ok=None,
                    enabled=lib.local_model_enabled,
                    automatic_analysis=lib.automatic_analysis,
                    can_enable=False,
                    can_analyze_existing=False,
                    can_rebuild=False,
                    embedding_index_label=embedding_label,
                )
            reason = self._provider_unavailable_reason(enabled=True) or "Model unavailable"
            return LocalAiStatus(
                kind=LocalAiStatusKind.ERROR,
                headline="Local AI model cannot run yet",
                detail=_friendly_provider_reason(reason),
                privacy_note=PRIVACY_NOTE,
                model_name=model_name,
                model_version=manifest.version,
                provider_label=provider_label,
                size_label=size_label,
                install_ready=True,
                install_blocked_reason=None,
                artifact_present=True,
                checksum_ok=checksum_ok,
                enabled=lib.local_model_enabled,
                automatic_analysis=lib.automatic_analysis,
                can_enable=False,
                can_analyze_existing=False,
                can_rebuild=False,
                embedding_index_label=embedding_label,
            )

        if not lib.local_model_enabled:
            return LocalAiStatus(
                kind=LocalAiStatusKind.INSTALLED_DISABLED,
                headline="Local AI installed — currently off",
                detail=(
                    "Enable Local AI to classify new Samples automatically and unlock "
                    "library backfill. Suggestions stay pending until you accept them."
                ),
                privacy_note=PRIVACY_NOTE,
                model_name=model_name,
                model_version=manifest.version,
                provider_label=provider_label,
                size_label=size_label,
                install_ready=False,
                install_blocked_reason=None,
                artifact_present=True,
                checksum_ok=True,
                enabled=False,
                automatic_analysis=lib.automatic_analysis,
                can_enable=True,
                can_analyze_existing=False,
                can_rebuild=True,
                embedding_index_label=embedding_label,
            )

        return LocalAiStatus(
            kind=LocalAiStatusKind.ENABLED,
            headline="Local AI enabled",
            detail=(
                f"{provider_label} · version {manifest.version}. "
                "New Samples can receive full local analysis when automatic analysis is on. "
                "Machine output stays a Suggestion until you accept or edit it."
            ),
            privacy_note=PRIVACY_NOTE,
            model_name=model_name,
            model_version=manifest.version,
            provider_label=provider_label,
            size_label=size_label,
            install_ready=False,
            install_blocked_reason=None,
            artifact_present=True,
            checksum_ok=True,
            enabled=True,
            automatic_analysis=lib.automatic_analysis,
            can_enable=True,
            can_analyze_existing=True,
            can_rebuild=True,
            embedding_index_label=embedding_label,
        )

    def set_enabled(self, enabled: bool) -> LocalAiStatus:
        status = self.status()
        if enabled and not status.can_enable and status.kind is not LocalAiStatusKind.ENABLED:
            raise ValidationError(
                "Local AI cannot be enabled until the model is installed and verified",
                detail=status.kind.value,
            )
        self._settings.update_library_analysis(local_model_enabled=bool(enabled))
        return self.status()

    def install_model(
        self,
        *,
        source: Path | str | None = None,
        overwrite: bool = False,
        cancel_check: CancelCheck | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        """Explicit install only. Never called during inference or scan."""
        status = self.status()
        if not status.install_ready and status.kind is not LocalAiStatusKind.ERROR:
            raise ValidationError(
                status.install_blocked_reason or "Model install is not available",
                detail=status.kind.value,
            )
        self._download_active = True

        def _progress(event: InstallProgress) -> None:
            if progress is not None:
                progress(event)

        try:
            return install_model_artifact(
                self._cache_dir,
                manifest=self._active_manifest(),
                source=source,
                overwrite=overwrite,
                cancel_check=cancel_check,
                progress=_progress,
            )
        finally:
            self._download_active = False

    def plan_backfill(self) -> BackfillPlan:
        status = self.status()
        if not status.can_analyze_existing:
            raise ValidationError(
                "Analyze Existing Library requires Local AI installed and enabled",
                detail=status.kind.value,
            )
        sample_ids = self.list_eligible_backfill_sample_ids()
        return BackfillPlan(
            sample_ids=tuple(sample_ids),
            sample_count=len(sample_ids),
            model_name=status.model_name,
            model_version=status.model_version,
            workload=workload_for_count(len(sample_ids)),
            depth=AnalysisDepth.FULL,
        )

    def queue_backfill(self, plan: BackfillPlan | None = None) -> EntityId:
        """Queue FULL analysis for eligible Samples missing valid semantic output."""
        resolved = plan if plan is not None else self.plan_backfill()
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to queue backfill analysis")
        if not resolved.sample_ids:
            raise ValidationError(
                "No Samples need Local AI analysis for the active model version",
            )
        scope: dict[str, object] = {
            "sample_ids": [str(sample_id) for sample_id in resolved.sample_ids],
            "depth": str(resolved.depth),
            "purpose": "semantic_backfill",
            "model_version": resolved.model_version,
            "workload": str(resolved.workload),
            "sample_count": resolved.sample_count,
        }
        if self._cache_dir is not None:
            scope["cache_dir"] = str(self._cache_dir)
        return self._scheduler.submit(JobSpec(type=JobType.DETERMINISTIC_ANALYSIS, scope=scope))

    def queue_rebuild_suggestions(self) -> EntityId:
        """Re-queue FULL analysis for Samples that already have semantic embeddings."""
        status = self.status()
        if not status.can_rebuild or not status.enabled:
            raise ValidationError(
                "Rebuild Suggestions requires Local AI installed and enabled",
                detail=status.kind.value,
            )
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to rebuild suggestions")
        sample_ids = self.list_samples_with_semantic_embeddings(status.model_version)
        if not sample_ids:
            raise ValidationError("No semantic embeddings available to rebuild Suggestions from")
        scope: dict[str, object] = {
            "sample_ids": [str(sample_id) for sample_id in sample_ids],
            "depth": AnalysisDepth.FULL.value,
            "purpose": "rebuild_suggestions",
            "model_version": status.model_version,
            "cache_dir": str(self._cache_dir),
        }
        return self._scheduler.submit(JobSpec(type=JobType.DETERMINISTIC_ANALYSIS, scope=scope))

    def queue_rebuild_similarity_index(self) -> EntityId:
        status = self.status()
        if not status.can_rebuild:
            raise ValidationError(
                "Rebuild Similarity Index requires a verified Local AI model",
                detail=status.kind.value,
            )
        if self._similarity is None:
            raise ValidationError("SimilarityService is required to rebuild the index")
        return self._similarity.rebuild_index()

    def list_eligible_backfill_sample_ids(self) -> list[EntityId]:
        """Online Samples missing a valid embedding for the active model version."""
        manifest = self._active_manifest()
        model_version = manifest.model_version
        store = self._embeddings
        if store is None:
            from koffer.analysis.embeddings import EmbeddingStore

            store = EmbeddingStore(self._cache_dir)

        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sources = SourceRepository(conn)
        eligible: list[EntityId] = []
        for sample in samples.list_by_availability(
            (SampleAvailability.ONLINE, SampleAvailability.CHANGED)
        ):
            if sample.source_id is None:
                continue
            source = sources.get(sample.source_id)
            if source is None:
                continue
            media = Path(source.root_path) / sample.relative_path
            if not media.is_file():
                continue
            fingerprint = f"{path_fingerprint(media)}:{content_fingerprint(media)}"
            existing = store.get(sample.id, model_version)
            if existing is not None and existing.source_fingerprint == fingerprint:
                continue
            eligible.append(sample.id)
        return eligible

    def list_samples_with_semantic_embeddings(self, model_version: str) -> list[EntityId]:
        store = self._embeddings
        if store is None:
            from koffer.analysis.embeddings import EmbeddingStore

            store = EmbeddingStore(self._cache_dir)
        conn = self._factory.get_connection()
        samples = SampleRepository(conn).list_by_availability(
            (SampleAvailability.ONLINE, SampleAvailability.CHANGED)
        )
        return [sample.id for sample in samples if store.get(sample.id, model_version) is not None]

    def _active_manifest(self) -> ModelManifest:
        if isinstance(self._provider, PannsSemanticProvider):
            return self._provider.manifest
        return load_model_manifest()

    def decide_discovery_depth(self) -> AnalysisDepth | None:
        lib = self._settings.load().library_analysis
        return discovery_analysis_depth(
            automatic_analysis=lib.automatic_analysis,
            local_model_enabled=lib.local_model_enabled,
            provider_available=self._provider_available(enabled=True),
        )

    def queue_discovery_analysis(self, sample_ids: list[EntityId]) -> EntityId | None:
        """Queue analysis after discovery/probe when settings permit."""
        if not sample_ids:
            return None
        depth = self.decide_discovery_depth()
        if depth is None:
            return None
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to queue discovery analysis")
        # Prefer AnalysisService when wired so cache_dir/depth stay consistent.
        if self._analysis is not None and len(sample_ids) == 1:
            return self._analysis.queue_for_sample(sample_ids[0], depth=depth)
        scope: dict[str, object] = {
            "sample_ids": [str(sample_id) for sample_id in sample_ids],
            "depth": str(depth),
            "purpose": "discovery_analysis",
            "cache_dir": str(self._cache_dir),
        }
        return self._scheduler.submit(JobSpec(type=JobType.DETERMINISTIC_ANALYSIS, scope=scope))

    def _provider_available(self, *, enabled: bool) -> bool:
        return self._provider_unavailable_reason(enabled=enabled) is None

    def _provider_unavailable_reason(self, *, enabled: bool) -> str | None:
        provider = self._provider
        if provider is None:
            return PannsSemanticProvider(self._cache_dir, enabled=enabled).unavailable_reason()
        if isinstance(provider, PannsSemanticProvider):
            # Probe with the requested enable flag without mutating AppContext state.
            # Preserve require_torch / injected runners from the shared provider.
            probe = PannsSemanticProvider(
                self._cache_dir,
                manifest=provider.manifest,
                artifact_path=provider.artifact_path,
                enabled=enabled,
                require_torch=provider._require_torch,  # noqa: SLF001
                inference_runner=provider._inference_runner,  # noqa: SLF001
            )
            return probe.unavailable_reason()
        if not enabled:
            return "Semantic provider is disabled"
        if not provider.is_available():
            return provider.unavailable_reason() or "Model unavailable"
        return None

    def _embedding_index_label(self, model_version: str) -> str:
        store = self._embeddings
        if store is None:
            from koffer.analysis.embeddings import EmbeddingStore

            store = EmbeddingStore(self._cache_dir)
        count = len(store.list_for_model(model_version))
        if count == 0:
            return "No similarity index yet"
        return f"{count} embedding{'s' if count != 1 else ''} indexed"


def _friendly_provider_reason(reason: str) -> str:
    lowered = reason.lower()
    if "torch" in lowered:
        return (
            "The optional machine-learning runtime is not installed. "
            "Install the semantic package extra, then retry from Settings."
        )
    if "not installed" in lowered or "weights" in lowered:
        return (
            "Model weights are not installed yet. Use Install Model when the checksum is recorded."
        )
    if "checksum" in lowered:
        return "The model file failed verification. Reinstall to repair it."
    return "Local AI is temporarily unavailable. Import and browsing still work."
