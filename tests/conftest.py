"""Shared pytest fixtures for Phase 0."""

from __future__ import annotations

import os

# Ensure Qt UI tests can run headless in CI and local make qa.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
