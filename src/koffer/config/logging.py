"""Application logging bootstrap."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from koffer.config.paths import AppPaths


def configure_logging(paths: AppPaths, *, level: int = logging.INFO) -> logging.Logger:
    """Configure root/application logging to a rotating file under XDG state."""
    paths.ensure()
    logger = logging.getLogger("koffer")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    log_path: Path = paths.log_dir / "koffer.log"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(stream)
    return logger
