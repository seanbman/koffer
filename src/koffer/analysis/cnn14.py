"""Minimal PANNs Cnn14 architecture for local inference (docs/19, docs/23).

Derived from the audited MIT ``qiuqiangkong/audioset_tagging_cnn`` Cnn14 reference.
Torch is imported lazily. Log-mel fronts the CNN body using librosa so the
optional semantic stack does not require torchlibrosa at runtime; official
checkpoint CNN/FC weights load by matching ``bn0`` / ``conv_block*`` / ``fc*``
state-dict keys.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np

from koffer.domain.errors import UnsupportedOperationError, ValidationError

__all__ = [
    "CNN14_CLASSES_NUM",
    "CNN14_EMBEDDING_DIM",
    "CNN14_MAX_SAMPLES",
    "CNN14_MIN_FRAMES",
    "CNN14_MIN_SAMPLES",
    "CNN14_SAMPLE_RATE_HZ",
    "Cnn14Params",
    "build_cnn14",
    "frame_waveform_for_cnn14",
    "load_audioset_class_labels",
    "load_cnn14_checkpoint",
    "logmel_from_waveform",
    "run_cnn14_forward",
    "waveform_from_audio_path",
]

CNN14_SAMPLE_RATE_HZ = 32_000
CNN14_CLASSES_NUM = 527
CNN14_EMBEDDING_DIM = 2048

# Official 32 kHz Cnn14 feature params (audioset_tagging_cnn defaults).
_WINDOW_SIZE = 1024
_HOP_SIZE = 320
_MEL_BINS = 64
_FMIN = 50
_FMAX = 14_000

# Cnn14 applies five stride-2 avg pools on the time axis before the final
# (1, 1) block. With librosa center=True framing, mel frames = 1 + n // hop.
# T >= 32 keeps the pooled time axis at least 1 (floor(T / 32) >= 1).
CNN14_MIN_FRAMES = 32
CNN14_MIN_SAMPLES = (CNN14_MIN_FRAMES - 1) * _HOP_SIZE  # 9920 @ 32 kHz (~0.31 s)
# Bounded window: AudioSet-style 10 s clip keeps long files deterministic/local.
CNN14_MAX_SAMPLES = CNN14_SAMPLE_RATE_HZ * 10


class Cnn14Params:
    """Frozen hyper-parameters for the V1 Cnn14 provider."""

    sample_rate_hz: int = CNN14_SAMPLE_RATE_HZ
    window_size: int = _WINDOW_SIZE
    hop_size: int = _HOP_SIZE
    mel_bins: int = _MEL_BINS
    fmin: int = _FMIN
    fmax: int = _FMAX
    classes_num: int = CNN14_CLASSES_NUM
    embedding_dim: int = CNN14_EMBEDDING_DIM
    min_frames: int = CNN14_MIN_FRAMES
    min_samples: int = CNN14_MIN_SAMPLES
    max_samples: int = CNN14_MAX_SAMPLES


def load_audioset_class_labels(path: Path | None = None) -> tuple[str, ...]:
    """Return the 527 AudioSet display names in checkpoint index order."""
    if path is not None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        root = resources.files("koffer.analysis.models")
        traversable = root.joinpath("audioset_class_labels.json")
        with resources.as_file(traversable) as mapped:
            payload = json.loads(Path(mapped).read_text(encoding="utf-8"))
    labels = payload.get("labels")
    if not isinstance(labels, list) or len(labels) != CNN14_CLASSES_NUM:
        raise ValidationError(
            "AudioSet class label table is invalid",
            detail=f"expected {CNN14_CLASSES_NUM} labels",
        )
    return tuple(str(item) for item in labels)


def waveform_from_audio_path(
    audio_path: Path, *, sample_rate_hz: int = CNN14_SAMPLE_RATE_HZ
) -> np.ndarray:
    """Decode supported audio to mono float32 at the Cnn14 sample rate."""
    path = Path(audio_path)
    if not path.is_file():
        raise ValidationError("Audio path is not a readable file", detail=str(path))
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover — librosa is a core dependency
        raise UnsupportedOperationError(
            "Audio decode dependency missing",
            detail="librosa is required for semantic inference",
        ) from exc
    try:
        waveform, _sr = librosa.load(str(path), sr=sample_rate_hz, mono=True)
    except Exception as exc:  # noqa: BLE001 — surface decode failures cleanly
        raise ValidationError(
            "Failed to decode audio for semantic inference",
            detail=f"{path}: {exc}",
        ) from exc
    arr = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if arr.size == 0:
        raise ValidationError("Decoded audio is empty", detail=str(path))
    return arr


def frame_waveform_for_cnn14(waveform: np.ndarray) -> np.ndarray:
    """Pad/truncate a mono waveform to a Cnn14-safe in-memory window.

    Short one-shots are zero-padded to ``CNN14_MIN_SAMPLES`` so the log-mel
    time axis stays at least ``CNN14_MIN_FRAMES`` before the six pooling
    stages. Longer clips are truncated to ``CNN14_MAX_SAMPLES`` (leading
    window). This never mutates source audio on disk.
    """
    y = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if y.size == 0:
        raise ValidationError("Decoded audio is empty", detail="waveform size 0")
    if y.size < CNN14_MIN_SAMPLES:
        padded = np.zeros(CNN14_MIN_SAMPLES, dtype=np.float32)
        padded[: y.size] = y
        return padded
    if y.size > CNN14_MAX_SAMPLES:
        return np.ascontiguousarray(y[:CNN14_MAX_SAMPLES], dtype=np.float32)
    return np.ascontiguousarray(y, dtype=np.float32)


def logmel_from_waveform(
    waveform: np.ndarray,
    *,
    sample_rate_hz: int = CNN14_SAMPLE_RATE_HZ,
    frame: bool = True,
) -> np.ndarray:
    """Compute log-mel features shaped ``(1, 1, time, mel)`` for Cnn14."""
    import librosa

    y = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if frame:
        y = frame_waveform_for_cnn14(y)
    mel = librosa.feature.melspectrogram(
        y=y,
        sr=sample_rate_hz,
        n_fft=_WINDOW_SIZE,
        hop_length=_HOP_SIZE,
        win_length=_WINDOW_SIZE,
        window="hann",
        center=True,
        pad_mode="reflect",
        n_mels=_MEL_BINS,
        fmin=_FMIN,
        fmax=_FMAX,
        power=2.0,
    )
    # Match torchlibrosa LogmelFilterBank log10 path used by upstream Cnn14.
    logmel = np.log10(np.maximum(mel, 1e-10)).astype(np.float32)
    # (mel, time) -> (batch, channel, time, mel)
    shaped = np.ascontiguousarray(logmel.T[np.newaxis, np.newaxis, :, :], dtype=np.float32)
    return shaped


def build_cnn14(*, classes_num: int = CNN14_CLASSES_NUM) -> Any:
    """Construct an untrained Cnn14 body (requires torch)."""
    torch = _import_torch()
    return _Cnn14(classes_num=classes_num, torch_mod=torch)


def load_cnn14_checkpoint(artifact_path: Path, *, classes_num: int = CNN14_CLASSES_NUM) -> Any:
    """Load Cnn14 CNN/FC weights from an official-style checkpoint file."""
    torch = _import_torch()
    path = Path(artifact_path)
    if not path.is_file():
        raise ValidationError("Model artifact is not a readable file", detail=str(path))
    try:
        # weights_only is preferred on modern torch; fall back for older builds.
        try:
            checkpoint = torch.load(str(path), map_location="cpu", weights_only=False)
        except TypeError:
            checkpoint = torch.load(str(path), map_location="cpu")
    except Exception as exc:  # noqa: BLE001 — corrupt/partial artifacts
        raise ValidationError(
            "Failed to load semantic model checkpoint",
            detail=f"{path}: {exc}",
        ) from exc

    state = checkpoint.get("model", checkpoint) if isinstance(checkpoint, dict) else checkpoint
    if not isinstance(state, dict):
        raise ValidationError(
            "Semantic model checkpoint has unexpected format",
            detail=str(path),
        )

    model = _Cnn14(classes_num=classes_num, torch_mod=torch)
    model_state = model.state_dict()
    filtered: dict[str, Any] = {}
    for key, value in state.items():
        if key in model_state and tuple(model_state[key].shape) == tuple(value.shape):
            filtered[key] = value
    if not filtered:
        raise ValidationError(
            "Semantic model checkpoint contained no compatible Cnn14 weights",
            detail=str(path),
        )
    missing = model.load_state_dict(filtered, strict=False)
    # Ignore unexpected (spectrogram/logmel/specaug) and intentionally absent buffers.
    _ = missing
    model.eval()
    return model


def run_cnn14_forward(
    model: Any,
    waveform: np.ndarray,
    *,
    class_labels: tuple[str, ...] | list[str],
    top_k: int = 10,
    sample_rate_hz: int = CNN14_SAMPLE_RATE_HZ,
) -> tuple[list[tuple[str, float]], np.ndarray]:
    """Run a Cnn14 forward pass; returns top-k ``(label, score)`` and L2 embedding."""
    torch = _import_torch()
    if top_k < 1:
        raise ValidationError("top_k must be >= 1", detail=str(top_k))
    if len(class_labels) != CNN14_CLASSES_NUM:
        raise ValidationError(
            "class_labels length must match Cnn14 classes",
            detail=str(len(class_labels)),
        )

    # Framing (pad/truncate) runs inside logmel_from_waveform before pooling.
    logmel = logmel_from_waveform(waveform, sample_rate_hz=sample_rate_hz)
    tensor = torch.from_numpy(np.ascontiguousarray(logmel))
    was_training = bool(getattr(model, "training", False))
    model.eval()
    try:
        with torch.no_grad():
            output = model(tensor)
    finally:
        if was_training:
            model.train()

    if not isinstance(output, dict) or "clipwise_output" not in output or "embedding" not in output:
        raise ValidationError("Cnn14 forward did not return clipwise_output/embedding")

    clipwise = _to_numpy1d(output["clipwise_output"])
    embedding = _to_numpy1d(output["embedding"])
    if clipwise.shape[0] != CNN14_CLASSES_NUM:
        raise ValidationError(
            "Cnn14 clipwise_output has unexpected size",
            detail=str(clipwise.shape),
        )
    if embedding.shape[0] != CNN14_EMBEDDING_DIM:
        raise ValidationError(
            "Cnn14 embedding has unexpected size",
            detail=str(embedding.shape),
        )

    k = min(top_k, clipwise.shape[0])
    top_indices = np.argsort(-clipwise)[:k]
    labels = [(str(class_labels[int(i)]), float(clipwise[int(i)])) for i in top_indices]
    norm = float(np.linalg.norm(embedding))
    if norm > 0.0:
        embedding = (embedding / norm).astype(np.float32)
    else:
        embedding = embedding.astype(np.float32)
    return labels, embedding


def _to_numpy1d(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 2 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    return arr.astype(np.float32)


def _import_torch() -> Any:
    try:
        import torch
    except ImportError as exc:
        raise UnsupportedOperationError(
            "Optional dependency 'torch' is not installed",
            detail="Install the semantic extra to enable local Cnn14 inference",
        ) from exc
    return torch


def _init_layer(layer: Any, torch_mod: Any) -> None:
    torch_mod.nn.init.xavier_uniform_(layer.weight)
    if getattr(layer, "bias", None) is not None:
        layer.bias.data.fill_(0.0)


def _init_bn(bn: Any) -> None:
    bn.bias.data.fill_(0.0)
    bn.weight.data.fill_(1.0)


def _make_conv_block(in_channels: int, out_channels: int, torch_mod: Any) -> Any:
    """Build one Cnn14 ConvBlock without importing torch at module load."""
    nn = torch_mod.nn
    functional = torch_mod.nn.functional
    module_base: Any = nn.Module

    class ConvBlock(module_base):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.conv1 = nn.Conv2d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=(3, 3),
                stride=(1, 1),
                padding=(1, 1),
                bias=False,
            )
            self.conv2 = nn.Conv2d(
                in_channels=out_channels,
                out_channels=out_channels,
                kernel_size=(3, 3),
                stride=(1, 1),
                padding=(1, 1),
                bias=False,
            )
            self.bn1 = nn.BatchNorm2d(out_channels)
            self.bn2 = nn.BatchNorm2d(out_channels)
            _init_layer(self.conv1, torch_mod)
            _init_layer(self.conv2, torch_mod)
            _init_bn(self.bn1)
            _init_bn(self.bn2)

        def forward(
            self,
            input: Any,
            pool_size: tuple[int, int] = (2, 2),
            pool_type: str = "avg",
        ) -> Any:
            x = functional.relu_(self.bn1(self.conv1(input)))
            x = functional.relu_(self.bn2(self.conv2(x)))
            if pool_type == "max":
                x = functional.max_pool2d(x, kernel_size=pool_size)
            elif pool_type == "avg":
                x = functional.avg_pool2d(x, kernel_size=pool_size)
            elif pool_type == "avg+max":
                x = functional.avg_pool2d(x, kernel_size=pool_size) + functional.max_pool2d(
                    x, kernel_size=pool_size
                )
            else:
                raise ValidationError("Incorrect Cnn14 pool_type", detail=pool_type)
            return x

    return ConvBlock()


def _Cnn14(*, classes_num: int, torch_mod: Any) -> Any:
    nn = torch_mod.nn
    functional = torch_mod.nn.functional
    torch = torch_mod
    module_base: Any = nn.Module

    class Cnn14(module_base):  # type: ignore[misc]
        """Cnn14 body accepting precomputed log-mel ``(B, 1, T, mel)``."""

        def __init__(self) -> None:
            super().__init__()
            self.bn0 = nn.BatchNorm2d(_MEL_BINS)
            self.conv_block1 = _make_conv_block(1, 64, torch)
            self.conv_block2 = _make_conv_block(64, 128, torch)
            self.conv_block3 = _make_conv_block(128, 256, torch)
            self.conv_block4 = _make_conv_block(256, 512, torch)
            self.conv_block5 = _make_conv_block(512, 1024, torch)
            self.conv_block6 = _make_conv_block(1024, 2048, torch)
            self.fc1 = nn.Linear(2048, 2048, bias=True)
            self.fc_audioset = nn.Linear(2048, classes_num, bias=True)
            _init_bn(self.bn0)
            _init_layer(self.fc1, torch)
            _init_layer(self.fc_audioset, torch)

        def forward(self, input: Any) -> dict[str, Any]:
            # input: (batch, 1, time, mel)
            x = input
            x = x.transpose(1, 3)
            x = self.bn0(x)
            x = x.transpose(1, 3)

            x = self.conv_block1(x, pool_size=(2, 2), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = self.conv_block2(x, pool_size=(2, 2), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = self.conv_block3(x, pool_size=(2, 2), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = self.conv_block4(x, pool_size=(2, 2), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = self.conv_block5(x, pool_size=(2, 2), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = self.conv_block6(x, pool_size=(1, 1), pool_type="avg")
            x = functional.dropout(x, p=0.2, training=self.training)
            x = torch.mean(x, dim=3)

            x1, _ = torch.max(x, dim=2)
            x2 = torch.mean(x, dim=2)
            x = x1 + x2
            x = functional.dropout(x, p=0.5, training=self.training)
            x = functional.relu_(self.fc1(x))
            embedding = functional.dropout(x, p=0.5, training=self.training)
            clipwise_output = torch.sigmoid(self.fc_audioset(x))
            return {"clipwise_output": clipwise_output, "embedding": embedding}

    return Cnn14()
