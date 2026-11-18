.PHONY: setup check install test lint format clean repro-check sbom

setup:
	uv sync --locked

check:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required; install uv 0.13.9 or any later 0.13.x and run 'make setup'." >&2; exit 127; }
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

# Build the committed source twice in fresh clones and compare SHA-256 of every artifact.
repro-check:
	python3 scripts/check_reproducible_build.py --build 'uv build --no-create-gitignore --out-dir {out}'

# CycloneDX SBOM of the locked runtime dependencies (what the release job attests).
sbom:
	uv export --preview-features sbom-export --format cyclonedx1.5 --locked --no-dev --all-extras --output-file fastmcp-builder.cdx.json
