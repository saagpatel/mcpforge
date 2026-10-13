# AGENTS.md

## Purpose

`mcpforge` is a Python 3.12+ CLI and MCP server that generates FastMCP servers from plain-English descriptions, then validates generated projects before they are trusted.

## Layout

- `src/mcpforge/` contains the CLI, MCP server, generation, validation, and templates.
- `tests/` contains the automated test suite.
- `examples/` contains generated Python and TypeScript examples.
- `docs/` contains provider and project documentation.

## Setup

- Python is pinned by `.python-version` to 3.12.15.
- uv 0.13.0 or later is required by `pyproject.toml` and pinned in CI.
- Run `make setup` to install the locked dependencies.
- The `.cursor/environment.json` setup uses `.cursor/install.sh`, which pins Python 3.12.15 and uv 0.13.0, syncs from `uv.lock`, and runs credential-free checks. Do not copy local credentials or configuration into Cloud. Hosted generation checks remain opt-in.
- For Codex Cloud, use the portable [MCP Forge Cloud workflow skill](.agents/skills/mcpforge-cloud-workflow/SKILL.md). Follow supplied startup instructions and use the existing isolated task checkout. Prepared startup permits authorized source edits and commits. Refresh installation only when the supplied procedure requires it; do not upgrade dependencies or change locks to bypass startup failures.

## Checks

- `make check` runs lockfile, lint, formatting, tests, build, and example validation checks without applying source fixes.
- The CI matrix covers verified Python 3.12 through 3.14 lanes. Python 3.15 is excluded because the locked `watchfiles` build currently uses PyO3 0.26, which supports up to Python 3.14.
- Hosted-provider smoke tests require explicit authorization and credentials; they are not part of credential-free checks.
- A green local or Cloud check does not establish hosted-provider, deployment, production, recovery, or human acceptance.

## Boundaries

- Generated MCP servers can widen local tool reach. Review generated code before installing it or wiring it into clients.
- Do not read provider keys, `.env` files, keychains, OAuth stores, browser profiles, raw logs, private transcripts, or credential-bearing configs.
- Cursor Cloud uses repo-local `.cursor/environment.json`; keep Cloud secrets in its environment-scoped Secrets settings only when explicitly authorized. Hosted generation checks stay opt-in.
- Codex Cloud settings, tools, credentials, browser sign-ins, and services may differ from local state. Preserve network, privacy, approval, and secret settings. Keep machine-specific infrastructure, personal memory, and secrets out of the repository.
- Keep PyPI/package naming, release state, and documentation synchronized before release work.

## Delivery

- Read the applicable project contract before pushing; never add a remote to a repository that has none.
- Keep changes scoped, preserve unrelated work, and report the checks actually run and any limits.
- Do not publish, tag, release, deploy, or widen access unless the task explicitly authorizes it.
