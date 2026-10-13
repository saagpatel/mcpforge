.PHONY: setup check install test lint format clean

setup:
	uv sync --locked

check:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required; install the pinned version (>=0.13.0) and run 'make setup'." >&2; exit 127; }
	uv lock --check
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .
	uv run --no-sync pytest
	@build_dir=".make-check-dist.$$$$"; trap 'rm -rf "$$build_dir"' EXIT; uv build --out-dir "$$build_dir"
# CI validation uses MCPFORGE_NO_SANDBOX because GitHub runners lack sandbox-exec.
	@if [ "$${CI:-}" = "true" ]; then \
	  MCPFORGE_NO_SANDBOX=1 uv run --no-sync mcpforge validate examples/todo-server; \
	else \
	  uv run --no-sync mcpforge validate examples/todo-server; \
	fi

install:
	uv sync --locked

test:
	uv run --no-sync pytest tests/ -v

lint:
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .

format:
	uv run --no-sync ruff check --fix .
	uv run --no-sync ruff format .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf dist/
