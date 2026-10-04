"""Filename/path token heuristics for deterministic Suggestions (docs/06, docs/19)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from koffer.analysis.evidence import build_evidence
from koffer.domain.enums import ClassificationDimension

# Musical metadata suggestion dimensions (not ClassificationDimension; library-only).
DIM_BPM = "bpm"
DIM_KEY = "key"

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+", re.IGNORECASE)
_BPM_RE = re.compile(r"(?<![a-z0-9])(\d{2,3})\s*bpm(?![a-z0-9])", re.IGNORECASE)
_KEY_RE = re.compile(
    r"(?<![a-z0-9])([a-g])\s*(#|b|sharp|flat)?\s*(maj(?:or)?|min(?:or)?|m)?(?![a-z0-9])",
    re.IGNORECASE,
)

# instrument_source / sample_type / musical_role / character token maps.
_INSTRUMENT_TOKENS: dict[str, tuple[str, float]] = {
    "kick": ("Kick", 0.97),
    "bd": ("Kick", 0.9),
    "bassdrum": ("Kick", 0.95),
    "808": ("Kick", 0.88),
    "snare": ("Snare", 0.96),
    "snr": ("Snare", 0.94),
    "sd": ("Snare", 0.88),
    "clap": ("Clap", 0.95),
    "clp": ("Clap", 0.9),
    "hihat": ("Hi-hat", 0.95),
    "hihats": ("Hi-hat", 0.94),
    "hat": ("Hi-hat", 0.88),
    "hh": ("Hi-hat", 0.85),
    "cymbal": ("Cymbal", 0.92),
    "ride": ("Cymbal", 0.85),
    "crash": ("Cymbal", 0.88),
    "perc": ("Percussion", 0.86),
    "percussion": ("Percussion", 0.92),
    "drums": ("Drum kit", 0.9),
    "drum": ("Drum kit", 0.85),
    "bass": ("Bass", 0.9),
    "sub": ("Bass", 0.8),
    "guitar": ("Guitar", 0.92),
    "gtr": ("Guitar", 0.88),
    "keys": ("Keys", 0.88),
    "piano": ("Piano", 0.93),
    "rhodes": ("Rhodes", 0.95),
    "organ": ("Organ", 0.92),
    "synth": ("Synth", 0.9),
    "pad": ("Synth", 0.78),
    "strings": ("Strings", 0.9),
    "brass": ("Brass", 0.9),
    "vox": ("Vocal", 0.94),
    "vocal": ("Vocal", 0.95),
    "vocals": ("Vocal", 0.95),
    "voice": ("Vocal", 0.9),
    "foley": ("Foley", 0.9),
    "field": ("Field recording", 0.82),
}

_SAMPLE_TYPE_TOKENS: dict[str, tuple[str, float]] = {
    "oneshot": ("One-shot", 0.96),
    "oneshots": ("One-shot", 0.95),
    "shot": ("One-shot", 0.8),
    "loop": ("Loop", 0.95),
    "loops": ("Loop", 0.94),
    "phrase": ("Phrase", 0.9),
    "stem": ("Stem", 0.9),
    "stems": ("Stem", 0.9),
    "track": ("Track", 0.82),
    "texture": ("Texture", 0.88),
    "ambience": ("Ambience", 0.9),
    "ambient": ("Ambience", 0.85),
    "sfx": ("SFX", 0.92),
    "fx": ("SFX", 0.8),
}

_ROLE_TOKENS: dict[str, tuple[str, float]] = {
    "perc": ("Percussive", 0.8),
    "percussive": ("Percussive", 0.9),
    "rhythmic": ("Rhythmic", 0.88),
    "melodic": ("Melodic", 0.9),
    "harmonic": ("Harmonic", 0.88),
    "chords": ("Harmonic", 0.86),
    "chord": ("Harmonic", 0.84),
    "atmosphere": ("Atmospheric", 0.88),
    "atmospheric": ("Atmospheric", 0.9),
    "transition": ("Transitional", 0.85),
    "riser": ("Transitional", 0.82),
    "fill": ("Transitional", 0.78),
    "effect": ("Effect", 0.85),
}

_CHARACTER_TOKENS: dict[str, tuple[str, float]] = {
    "dark": ("Dark", 0.85),
    "bright": ("Bright", 0.85),
    "warm": ("Warm", 0.85),
    "cold": ("Cold", 0.85),
    "clean": ("Clean", 0.82),
    "dirty": ("Dirty", 0.82),
    "lofi": ("Lo-fi", 0.88),
    "acoustic": ("Acoustic", 0.85),
    "electronic": ("Electronic", 0.85),
    "distorted": ("Distorted", 0.85),
    "dry": ("Dry", 0.8),
    "wet": ("Wet", 0.8),
    "soft": ("Soft", 0.8),
    "aggressive": ("Aggressive", 0.85),
}

_GENRE_TOKENS: dict[str, tuple[str, float]] = {
    "hiphop": ("Hip-hop", 0.88),
    "house": ("House", 0.88),
    "techno": ("Techno", 0.88),
    "jungle": ("Jungle", 0.9),
    "dnb": ("Drum and bass", 0.9),
    "drumandbass": ("Drum and bass", 0.9),
    "ambient": ("Ambient", 0.85),
    "funk": ("Funk", 0.88),
    "soul": ("Soul", 0.88),
    "rock": ("Rock", 0.85),
    "jazz": ("Jazz", 0.88),
}


@dataclass(frozen=True, slots=True)
class HeuristicProposal:
    """One deterministic Suggestion candidate before persistence."""

    dimension: str
    proposed_value: str
    confidence: float
    evidence_json: str


def _normalize_tokens(relative_path: str, filename: str) -> tuple[list[str], list[str]]:
    path = PurePosixPath(relative_path.replace("\\", "/"))
    folder_parts = [part for part in path.parts[:-1] if part not in {".", ".."}]
    stem = PurePosixPath(filename).stem
    filename_tokens = [t for t in _TOKEN_SPLIT.split(stem.lower()) if t]
    folder_tokens: list[str] = []
    for part in folder_parts:
        folder_tokens.extend(t for t in _TOKEN_SPLIT.split(part.lower()) if t)
    return filename_tokens, folder_tokens


def _best_match(
    filename_tokens: list[str],
    folder_tokens: list[str],
    table: dict[str, tuple[str, float]],
    *,
    channel: str,
) -> HeuristicProposal | None:
    best: HeuristicProposal | None = None
    for token in filename_tokens:
        hit = table.get(token)
        if hit is None:
            continue
        value, score = hit
        # Filename evidence is slightly stronger than folder-only.
        confidence = min(1.0, score)
        evidence = build_evidence(
            filename={"label": value, "score": confidence, "token": token, "channel": channel}
        )
        candidate = HeuristicProposal(
            dimension=_dimension_for_channel(channel),
            proposed_value=value,
            confidence=confidence,
            evidence_json=evidence,
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    for token in folder_tokens:
        hit = table.get(token)
        if hit is None:
            continue
        value, score = hit
        confidence = min(1.0, max(0.0, score - 0.05))
        evidence = build_evidence(
            folder={"label": value, "score": confidence, "token": token, "channel": channel}
        )
        candidate = HeuristicProposal(
            dimension=_dimension_for_channel(channel),
            proposed_value=value,
            confidence=confidence,
            evidence_json=evidence,
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    return best


def _dimension_for_channel(channel: str) -> str:
    mapping = {
        "instrument_source": ClassificationDimension.INSTRUMENT_SOURCE.value,
        "sample_type": ClassificationDimension.SAMPLE_TYPE.value,
        "musical_role": ClassificationDimension.MUSICAL_ROLE.value,
        "character": ClassificationDimension.CHARACTER.value,
        "genre_style": ClassificationDimension.GENRE_STYLE.value,
    }
    return mapping[channel]


def _extract_bpm(text: str) -> HeuristicProposal | None:
    match = _BPM_RE.search(text)
    if match is None:
        return None
    bpm = int(match.group(1))
    if bpm < 40 or bpm > 300:
        return None
    confidence = 0.92
    return HeuristicProposal(
        dimension=DIM_BPM,
        proposed_value=str(bpm),
        confidence=confidence,
        evidence_json=build_evidence(
            filename={"label": f"{bpm}", "score": confidence, "token": match.group(0)}
        ),
    )


def _normalize_key(root: str, accidental: str | None, mode: str | None) -> str | None:
    note = root.upper()
    acc = (accidental or "").lower()
    if acc in {"#", "sharp"}:
        note = f"{note}#"
    elif acc in {"b", "flat"}:
        note = f"{note}b"
    mode_raw = (mode or "").lower()
    if mode_raw in {"", "maj", "major"}:
        # Bare note with no mode marker is too ambiguous unless accidental present —
        # still accept common filename keys like "Cm" / "Cmin" / "Cmaj".
        if mode is None:
            return None
        suffix = "maj"
    elif mode_raw in {"m", "min", "minor"}:
        suffix = "min"
    else:
        return None
    return f"{note}{suffix}"


def _extract_key(text: str) -> HeuristicProposal | None:
    for match in _KEY_RE.finditer(text):
        # Prefer matches that include an explicit mode token (m/min/maj).
        if match.group(3) is None:
            continue
        normalized = _normalize_key(match.group(1), match.group(2), match.group(3))
        if normalized is None:
            continue
        confidence = 0.9
        return HeuristicProposal(
            dimension=DIM_KEY,
            proposed_value=normalized,
            confidence=confidence,
            evidence_json=build_evidence(
                filename={"label": normalized, "score": confidence, "token": match.group(0)}
            ),
        )
    return None


def propose_from_path(*, relative_path: str, filename: str) -> list[HeuristicProposal]:
    """Return deterministic Suggestion proposals from path/filename tokens."""
    filename_tokens, folder_tokens = _normalize_tokens(relative_path, filename)
    proposals: list[HeuristicProposal] = []

    for channel, table in (
        ("instrument_source", _INSTRUMENT_TOKENS),
        ("sample_type", _SAMPLE_TYPE_TOKENS),
        ("musical_role", _ROLE_TOKENS),
        ("character", _CHARACTER_TOKENS),
        ("genre_style", _GENRE_TOKENS),
    ):
        hit = _best_match(filename_tokens, folder_tokens, table, channel=channel)
        if hit is not None:
            proposals.append(hit)

    haystack = f"{relative_path} {filename}"
    bpm = _extract_bpm(haystack)
    if bpm is not None:
        proposals.append(bpm)
    key = _extract_key(haystack)
    if key is not None:
        proposals.append(key)

    # Deduplicate by dimension keeping highest confidence.
    by_dim: dict[str, HeuristicProposal] = {}
    for proposal in proposals:
        existing = by_dim.get(proposal.dimension)
        if existing is None or proposal.confidence > existing.confidence:
            by_dim[proposal.dimension] = proposal
    return list(by_dim.values())
