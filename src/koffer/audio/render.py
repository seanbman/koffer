"""Argv-safe FFmpeg render pipeline from typed preparation recipes (docs/19)."""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from koffer.domain.errors import UnsupportedOperationError, ValidationError
from koffer.domain.preparation import PreparationRecipe

RENDER_PIPELINE_VERSION = "ffmpeg-filter-v1"


class FfmpegError(Exception):
    """FFmpeg invocation or render failure for one media path."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


class FfmpegNotFoundError(FfmpegError):
    """ffmpeg binary is not available on PATH."""


@dataclass(frozen=True, slots=True)
class RenderCommand:
    """Shell-free argv plus filter graph for diagnostics."""

    argv: tuple[str, ...]
    filter_graph: str
    output_path: Path


def resolve_ffmpeg() -> str | None:
    """Return absolute ffmpeg path via ``shutil.which``, or None if absent."""
    return shutil.which("ffmpeg")


def _atempo_chain(ratio: float) -> list[str]:
    """Split extreme ratios into chained atempo filters (each within 0.5–2.0)."""
    if abs(ratio - 1.0) < 1e-9:
        return []
    remaining = float(ratio)
    parts: list[str] = []
    # Guard against pathological values.
    if remaining <= 0:
        raise ValidationError("time_stretch_ratio must be > 0")
    while remaining > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.8g}")
    return parts


def build_filter_graph(
    recipe: PreparationRecipe,
    *,
    source_sample_rate_hz: int | None = None,
) -> str:
    """Build authoritative FFmpeg filter graph from typed recipe values (docs/19)."""
    recipe.validate()
    filters: list[str] = []

    # 2. trim
    start_s = recipe.trim.start_ms / 1000.0
    if recipe.trim.end_ms is None:
        if recipe.trim.start_ms > 0:
            filters.append(f"atrim=start={start_s:.6f},asetpts=PTS-STARTPTS")
    else:
        end_s = recipe.trim.end_ms / 1000.0
        filters.append(f"atrim=start={start_s:.6f}:end={end_s:.6f},asetpts=PTS-STARTPTS")

    # 3. reverse
    if recipe.reverse:
        filters.append("areverse")

    # 4. time stretch
    filters.extend(_atempo_chain(recipe.time_stretch_ratio))

    # 5. pitch shift (semitones + cents) via asetrate + aresample + atempo compensation
    total_cents = recipe.transpose_semitones * 100.0 + float(recipe.fine_cents)
    if abs(total_cents) > 1e-9:
        if source_sample_rate_hz and source_sample_rate_hz > 0:
            rate = source_sample_rate_hz
        else:
            rate = 44100
        factor = 2.0 ** (total_cents / 1200.0)
        new_rate = int(round(rate * factor))
        filters.append(f"asetrate={new_rate}")
        filters.append(f"aresample={rate}")
        # Restore duration after rate-change pitch shift.
        filters.extend(_atempo_chain(1.0 / factor))

    # 6. fades (fade-out via reverse+fade-in+reverse so duration need not be known a priori)
    if recipe.fade_in_ms > 0:
        filters.append(f"afade=t=in:st=0:d={recipe.fade_in_ms / 1000.0:.6f}")
    if recipe.fade_out_ms > 0:
        fade_out_s = recipe.fade_out_ms / 1000.0
        filters.append(f"areverse,afade=t=in:st=0:d={fade_out_s:.6f},areverse")

    # 7. gain / normalize
    if abs(recipe.gain_db) > 1e-9:
        filters.append(f"volume={recipe.gain_db:.6f}dB")
    if recipe.normalize.enabled:
        # Peak-oriented loudnorm target; TP is true-peak ceiling in dBFS.
        tp = recipe.normalize.target_peak_dbfs
        filters.append(f"loudnorm=I=-16:TP={tp:.2f}:LRA=11")

    # 8. channel conversion
    if recipe.channels == "mono":
        filters.append("aformat=channel_layouts=mono")
    elif recipe.channels == "stereo":
        filters.append("aformat=channel_layouts=stereo")

    # 9. resample
    if recipe.sample_rate_hz != "source":
        filters.append(f"aresample={int(recipe.sample_rate_hz)}")

    if not filters:
        # Identity graph keeps `-af` consistent for argv construction/tests.
        return "anull"
    return ",".join(filters)


def _encoder_args(recipe: PreparationRecipe) -> list[str]:
    fmt = recipe.output_format
    if fmt == "wav":
        args = ["-f", "wav"]
        if recipe.bit_depth == 24:
            args.extend(["-c:a", "pcm_s24le"])
        elif recipe.bit_depth == 32:
            args.extend(["-c:a", "pcm_s32le"])
        else:
            args.extend(["-c:a", "pcm_s16le"])
        return args
    if fmt == "flac":
        return ["-f", "flac", "-c:a", "flac"]
    if fmt == "ogg":
        return ["-f", "ogg", "-c:a", "libvorbis", "-q:a", "5"]
    if fmt == "mp3":
        return ["-f", "mp3", "-c:a", "libmp3lame", "-q:a", "2"]
    raise ValidationError(f"unsupported output_format: {fmt}")


def build_render_command(
    source: Path,
    output: Path,
    recipe: PreparationRecipe,
    *,
    ffmpeg_bin: str | None = None,
    source_sample_rate_hz: int | None = None,
) -> RenderCommand:
    """Construct argv list for FFmpeg with ``shell=False`` safety (docs/19)."""
    recipe.validate()
    binary = ffmpeg_bin if ffmpeg_bin is not None else resolve_ffmpeg()
    if binary is None:
        raise FfmpegNotFoundError("ffmpeg not found on PATH", path=Path(source))

    src = Path(source)
    dst = Path(output)
    if src.resolve() == dst.resolve():
        raise ValidationError("render destination must differ from source path")

    filter_graph = build_filter_graph(recipe, source_sample_rate_hz=source_sample_rate_hz)
    argv = [
        binary,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-af",
        filter_graph,
        *_encoder_args(recipe),
        str(dst),
    ]
    return RenderCommand(argv=tuple(argv), filter_graph=filter_graph, output_path=dst)


def run_ffmpeg_render(
    source: Path,
    output: Path,
    recipe: PreparationRecipe,
    *,
    ffmpeg_bin: str | None = None,
    source_sample_rate_hz: int | None = None,
    timeout: float = 120.0,
) -> Path:
    """Render ``source`` through the recipe into ``output`` via argv + shell=False."""
    command = build_render_command(
        source,
        output,
        recipe,
        ffmpeg_bin=ffmpeg_bin,
        source_sample_rate_hz=source_sample_rate_hz,
    )
    dst = command.output_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            list(command.argv),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FfmpegError(f"ffmpeg timed out after {timeout}s", path=Path(source)) from exc
    except OSError as exc:
        raise FfmpegError(f"ffmpeg could not be executed: {exc}", path=Path(source)) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise FfmpegError(
            f"ffmpeg failed ({completed.returncode}): {detail or 'no stderr'}",
            path=Path(source),
        )
    if not dst.is_file() or dst.stat().st_size <= 0:
        raise FfmpegError("ffmpeg produced no output file", path=dst)
    return dst


def ensure_ffmpeg_available() -> str:
    """Return ffmpeg path or raise UnsupportedOperationError."""
    binary = resolve_ffmpeg()
    if binary is None:
        raise UnsupportedOperationError("ffmpeg is not available on PATH")
    return binary


def pitch_factor(semitones: float, fine_cents: int = 0) -> float:
    """Helper for tests: pitch ratio from semitones + cents."""
    return math.pow(2.0, (semitones * 100.0 + float(fine_cents)) / 1200.0)
