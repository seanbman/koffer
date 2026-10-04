"""XDG-compatible application path resolution via platformdirs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs

_APP_NAME = "koffer"
_APP_AUTHOR = "seanbman"


@dataclass(frozen=True)
class AppPaths:
    """Resolved writable locations for config, data, cache, and logs."""

    config_dir: Path
    data_dir: Path
    cache_dir: Path
    state_dir: Path
    log_dir: Path

    def ensure(self) -> AppPaths:
        """Create application directories if missing; never touches user media."""
        for path in (
            self.config_dir,
            self.data_dir,
            self.cache_dir,
            self.state_dir,
            self.log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return self


def resolve_app_paths() -> AppPaths:
    """Resolve XDG/platformdirs locations for the Koffer application."""
    dirs = PlatformDirs(appname=_APP_NAME, appauthor=_APP_AUTHOR)
    state_dir = Path(dirs.user_state_dir)
    return AppPaths(
        config_dir=Path(dirs.user_config_dir),
        data_dir=Path(dirs.user_data_dir),
        cache_dir=Path(dirs.user_cache_dir),
        state_dir=state_dir,
        log_dir=state_dir / "logs",
    )
