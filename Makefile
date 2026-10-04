.PHONY: lint typecheck test qa clean package package-stage licenses

lint:
	uv run --no-sync python -m ruff check .
	uv run --no-sync python -m ruff format --check .

typecheck:
	uv run --no-sync python -m mypy src/koffer

test:
	QT_QPA_PLATFORM=offscreen uv run --no-sync python -m pytest -q

qa: lint typecheck test

licenses:
	uv run --no-sync python scripts/verify_licenses.py --check-only

# Full packaging path. Fails with actionable dependency messaging when
# PyInstaller/appimagetool/uv extras are missing (see scripts/build_appimage.sh).
package:
	./scripts/build_appimage.sh
	./scripts/smoke_appimage.sh

# Stage AppDir without requiring appimagetool (CI/local partial builds).
package-stage:
	./scripts/build_appimage.sh --skip-appimage
	./scripts/smoke_appimage.sh dist/Koffer.AppDir

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	rm -f THIRD_PARTY_NOTICES.txt
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
