.PHONY: lint typecheck test qa clean

lint:
	uv run --no-sync python -m ruff check .
	uv run --no-sync python -m ruff format --check .

typecheck:
	uv run --no-sync python -m mypy src/koffer

test:
	QT_QPA_PLATFORM=offscreen uv run --no-sync python -m pytest -q

qa: lint typecheck test

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
