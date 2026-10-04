# 26. Command Reference

## Purpose

These are the command surfaces the implementation must provide so agents and humans use one predictable workflow.

## Bootstrap

~~~bash
uv sync --frozen --all-extras
~~~

For initial lock creation only:
~~~bash
uv lock
uv sync --all-extras
~~~

## Run

~~~bash
uv run koffer
~~~

Equivalent module entry:
~~~bash
uv run python -m koffer
~~~

Safe mode:
~~~bash
uv run koffer --safe-mode
~~~

## Quality

~~~bash
make lint
make typecheck
make test
make qa
~~~

Required Make targets:

### make lint
~~~bash
uv run ruff check .
uv run ruff format --check .
~~~

### make typecheck
~~~bash
uv run mypy src/koffer
~~~

### make test
~~~bash
uv run pytest -q
~~~

### make qa
Runs lint + typecheck + full tests.

## Test subsets

~~~bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/ui
uv run pytest tests/e2e
uv run pytest tests/performance
~~~

Qt headless:
~~~bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/ui
~~~

## Coverage

~~~bash
uv run coverage run -m pytest
uv run coverage report
~~~

## Generate fixtures

~~~bash
uv run python scripts/generate_test_audio.py
~~~

Generated fixtures must be deterministic.

## Database

Developer/test-only commands exposed through module tooling:

~~~bash
uv run python -m koffer.dev db-info
uv run python -m koffer.dev db-migrate
uv run python -m koffer.dev db-integrity
~~~

Do not require end users to run these.

## Model

~~~bash
uv run python -m koffer.dev model-manifest-check
uv run python -m koffer.dev model-smoke
~~~

Normal user model installation happens in Settings, not terminal.

## Package

~~~bash
make package
~~~

Expected internal steps:
~~~bash
scripts/build_appimage.sh
scripts/smoke_appimage.sh dist/Koffer-*.AppImage
~~~

## Clean

~~~bash
make clean
~~~

May remove:
- build output;
- test cache;
- generated temporary artifacts.

Must never remove user XDG data.

## CI parity

Every CI command must be runnable locally through the same Make/script entry points. Avoid CI-only magic.

## Dreadnought

Dreadnought command names may evolve. The required semantic operations are:
- initialize campaign against Koffer dev;
- seed scratch;
- dispatch Cursor Project Arm with an Order;
- collect result;
- verify;
- promote;
- evaluate/Grapher;
- report tokens;
- continue.

If the installed Dreadnought exposes `.dreadnought/bin/dispatch-cursor-arm.py`, use it rather than bypassing the control plane.
