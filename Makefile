.PHONY: repo-guard lint typecheck test qa clean package package-stage licenses

repo-guard:
	@tracked="$$(git ls-files | grep -E '^\.grapher(/|$$)' || true)"; \
	if [ -n "$$tracked" ]; then \
		echo "ERROR: tracked .grapher state is forbidden."; \
		echo "Grapher is local Dreadnought control-plane state, not Koffer source."; \
		echo "$$tracked"; \
		exit 1; \
	fi

lint:
	uv run --no-sync python -m ruff check .
	uv run --no-sync python -m ruff format --check --diff .

typecheck:
	uv run --no-sync python -m mypy src/koffer

test:
	QT_QPA_PLATFORM=offscreen uv run --no-sync python -m pytest -q

qa: repo-guard lint typecheck test

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
