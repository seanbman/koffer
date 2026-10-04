"""Deterministic analysis pipeline: heuristics + BPM/key → features/proposals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koffer.analysis.bpm_key import BPM_KEY_PROVIDER_VERSION, estimate_bpm_key, feature_payload
from koffer.analysis.evidence import build_evidence
from koffer.analysis.heuristics import DIM_BPM, DIM_KEY, HeuristicProposal, propose_from_path

DETERMINISTIC_PIPELINE_VERSION = "deterministic-v1"
DETERMINISTIC_PROVIDER = "deterministic"
DETERMINISTIC_PROVIDER_VERSION = "path-heuristics+librosa-v1"


@dataclass(frozen=True, slots=True)
class AnalysisFeatureDraft:
    name: str
    value_json: str
    provider_version: str


@dataclass(frozen=True, slots=True)
class DeterministicAnalysisResult:
    """In-memory result of one deterministic analysis pass (not yet persisted)."""

    proposals: tuple[HeuristicProposal, ...]
    features: tuple[AnalysisFeatureDraft, ...]
    pipeline_version: str = DETERMINISTIC_PIPELINE_VERSION
    provider: str = DETERMINISTIC_PROVIDER
    provider_version: str = DETERMINISTIC_PROVIDER_VERSION
    bpm_key_ok: bool = True
    bpm_key_error: str | None = None


def run_deterministic_analysis(
    *,
    relative_path: str,
    filename: str,
    media_path: Path | None,
) -> DeterministicAnalysisResult:
    """Compute Suggestions + analysis features. Never mutates media or classifications."""
    proposals = list(propose_from_path(relative_path=relative_path, filename=filename))
    features: list[AnalysisFeatureDraft] = []

    bpm_key_ok = True
    bpm_key_error: str | None = None

    if media_path is not None and media_path.is_file():
        dsp = estimate_bpm_key(media_path)
        bpm_key_ok = dsp.ok
        bpm_key_error = dsp.error_code
        if dsp.bpm is not None:
            features.append(
                AnalysisFeatureDraft(
                    name="bpm",
                    value_json=feature_payload("bpm", dsp.bpm.bpm),
                    provider_version=BPM_KEY_PROVIDER_VERSION,
                )
            )
            # Prefer path BPM when present; otherwise surface DSP estimate as Suggestion.
            if not any(p.dimension == DIM_BPM for p in proposals):
                proposals.append(
                    HeuristicProposal(
                        dimension=DIM_BPM,
                        proposed_value=str(int(round(dsp.bpm.bpm))),
                        confidence=dsp.bpm.confidence,
                        evidence_json=build_evidence(
                            dsp={
                                "bpm": dsp.bpm.bpm,
                                "score": dsp.bpm.confidence,
                                "provider_version": BPM_KEY_PROVIDER_VERSION,
                            }
                        ),
                    )
                )
        if dsp.key is not None:
            features.append(
                AnalysisFeatureDraft(
                    name="key",
                    value_json=feature_payload("key", dsp.key.key),
                    provider_version=BPM_KEY_PROVIDER_VERSION,
                )
            )
            if not any(p.dimension == DIM_KEY for p in proposals):
                proposals.append(
                    HeuristicProposal(
                        dimension=DIM_KEY,
                        proposed_value=dsp.key.key,
                        confidence=dsp.key.confidence,
                        evidence_json=build_evidence(
                            dsp={
                                "key": dsp.key.key,
                                "score": dsp.key.confidence,
                                "provider_version": BPM_KEY_PROVIDER_VERSION,
                            }
                        ),
                    )
                )

    # Path-derived BPM/key also become searchable analysis features when DSP absent.
    for proposal in proposals:
        if proposal.dimension == DIM_BPM and not any(f.name == "bpm" for f in features):
            try:
                bpm_val = float(proposal.proposed_value)
            except ValueError:
                continue
            features.append(
                AnalysisFeatureDraft(
                    name="bpm",
                    value_json=feature_payload("bpm", bpm_val),
                    provider_version=DETERMINISTIC_PROVIDER_VERSION,
                )
            )
        if proposal.dimension == DIM_KEY and not any(f.name == "key" for f in features):
            features.append(
                AnalysisFeatureDraft(
                    name="key",
                    value_json=feature_payload("key", proposal.proposed_value),
                    provider_version=DETERMINISTIC_PROVIDER_VERSION,
                )
            )

    return DeterministicAnalysisResult(
        proposals=tuple(proposals),
        features=tuple(features),
        bpm_key_ok=bpm_key_ok,
        bpm_key_error=bpm_key_error,
    )
