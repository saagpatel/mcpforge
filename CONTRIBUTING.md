# Contributing to mcpforge

Thank you for your interest in contributing! This document covers how to set up the project locally, run tests, and submit a pull request.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)

## Local Setup

```bash
# Clone the repository
git clone https://github.com/saagpatel/mcpforge.git
cd mcpforge

# Install all dependencies (including dev extras)
uv sync

# Verify the install
uv run mcpforge --help
```

## Running Tests

```bash
# Run the full test suite
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_generator.py -v
```

## Linting and Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix lint errors
uv run ruff check --fix .

# Format code
uv run ruff format .
```

Or use the Makefile shortcuts:

```bash
make lint    # ruff check
make test    # pytest
make install # uv sync
```

## Project Structure

```
src/mcpforge/       # Main package
  cli.py            # Click CLI entrypoint
  generator.py      # Core code-generation logic
  mcp_server.py     # FastMCP server mode
  templates/        # Jinja2 server templates
tests/              # pytest test suite
examples/           # Usage examples
```

## Submitting a Pull Request

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Make your changes.** Keep commits small and focused.
3. **Add or update tests** for any changed behavior. All tests must pass.
4. **Run lint** (`make lint`) and fix any issues before pushing.
5. **Open a PR** against `main` and fill out the pull request template.

## Commit Message Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | When to use |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `chore:` | Tooling, dependencies, CI |
| `docs:` | Documentation only |
| `test:` | Tests only |
| `refactor:` | Code change that neither fixes a bug nor adds a feature |

## Code of Conduct

Please be respectful in all interactions. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
