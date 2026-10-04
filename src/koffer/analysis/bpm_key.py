"""Librosa BPM/key baseline estimators (docs/19). Versioned parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

BPM_KEY_PROVIDER_VERSION = "librosa-bpm-key-v1"
# Target sample rate for analysis load (docs/19 baseline).
_ANALYSIS_SR = 22050
_KEY_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Krumhansl-Schmuckler major/minor profiles (rotated per tonic).
_MAJOR_PROFILE = (
    6.35,
    2.23,
    3.48,
    2.33,
    4.38,
    4.09,
    2.52,
    5.19,
    2.39,
    3.66,
    2.29,
    2.88,
)
_MINOR_PROFILE = (
    6.33,
    2.68,
    3.52,
    5.38,
    2.60,
    3.53,
    2.54,
    4.75,
    3.98,
    2.69,
    3.34,
    3.17,
)


@dataclass(frozen=True, slots=True)
class BpmEstimate:
    bpm: float
    confidence: float


@dataclass(frozen=True, slots=True)
class KeyEstimate:
    key: str
    confidence: float


@dataclass(frozen=True, slots=True)
class BpmKeyResult:
    bpm: BpmEstimate | None
    key: KeyEstimate | None
    provider_version: str = BPM_KEY_PROVIDER_VERSION
    ok: bool = True
    error_code: str | None = None


def _rotate(profile: tuple[float, ...], shift: int) -> list[float]:
    return list(profile[shift:] + profile[:shift])


def _correlation(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        return 0.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    num = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    den_a = sum((x - mean_a) ** 2 for x in a) ** 0.5
    den_b = sum((y - mean_b) ** 2 for y in b) ** 0.5
    if den_a == 0.0 or den_b == 0.0:
        return 0.0
    return float(num / (den_a * den_b))


def estimate_key_from_chroma(chroma_mean: list[float]) -> KeyEstimate | None:
    """Map a 12-bin chroma mean vector to major/minor key + confidence."""
    if len(chroma_mean) != 12:
        return None
    best_key = "Cmaj"
    best_score = float("-inf")
    second = float("-inf")
    for tonic in range(12):
        for mode, profile in (("maj", _MAJOR_PROFILE), ("min", _MINOR_PROFILE)):
            score = _correlation(chroma_mean, _rotate(profile, tonic))
            label = f"{_KEY_NAMES[tonic]}{mode}"
            if score > best_score:
                second = best_score
                best_score = score
                best_key = label
            elif score > second:
                second = score
    # Map correlation margin into a conservative [0.35, 0.9] confidence band.
    margin = max(0.0, best_score - second)
    confidence = max(0.35, min(0.9, 0.45 + margin))
    return KeyEstimate(key=best_key, confidence=float(confidence))


def estimate_bpm_key(path: Path) -> BpmKeyResult:
    """Load audio via librosa and estimate BPM + key. Never mutates ``path``."""
    try:
        import librosa
        import numpy as np
    except ImportError as exc:  # pragma: no cover - dependency must be present in qa
        return BpmKeyResult(
            bpm=None,
            key=None,
            ok=False,
            error_code=f"import_error:{exc}",
        )

    try:
        y, sr = librosa.load(str(path), sr=_ANALYSIS_SR, mono=True)
    except Exception as exc:  # noqa: BLE001 — analysis must not crash the Job
        return BpmKeyResult(
            bpm=None,
            key=None,
            ok=False,
            error_code=f"load_failed:{type(exc).__name__}",
        )

    if y.size == 0 or float(np.max(np.abs(y))) < 1e-8:
        return BpmKeyResult(bpm=None, key=None, ok=True, error_code="silence_or_empty")

    duration_s = float(y.size) / float(sr)
    # Short one-shots: path heuristics dominate; skip expensive DSP.
    if duration_s < 0.75:
        return BpmKeyResult(bpm=None, key=None, ok=True, error_code="too_short_for_dsp")

    bpm_est: BpmEstimate | None = None
    key_est: KeyEstimate | None = None

    try:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        tempo_value = float(np.atleast_1d(tempo)[0]) if tempo is not None else 0.0
        if tempo_value > 0:
            # Confidence rises with beat count; short loops stay moderate.
            beat_count = int(len(beat_frames))
            confidence = max(0.2, min(0.85, 0.25 + 0.05 * beat_count))
            bpm_est = BpmEstimate(bpm=round(tempo_value, 2), confidence=float(confidence))
    except Exception:  # noqa: BLE001
        bpm_est = None

    try:
        # chroma_stft is faster/stabler than chroma_cqt for V1 baseline.
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = [float(v) for v in np.mean(chroma, axis=1)]
        key_est = estimate_key_from_chroma(chroma_mean)
    except Exception:  # noqa: BLE001
        key_est = None

    return BpmKeyResult(bpm=bpm_est, key=key_est, ok=True)


def feature_payload(name: str, value: Any) -> str:
    """Serialize an analysis_features.value_json payload."""
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)
