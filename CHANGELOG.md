# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes.

## [0.3.3] - 2026-06-20

### Added

- `mcpforge demo`: generate a complete, validated weather MCP server with no API
  key and no spend. It runs the real plan → generate → validate pipeline against
  a built-in recording (a replay client serving a packaged cassette), so new
  users can see exactly what mcpforge produces before configuring a provider.
- OpenRouter provider (`--provider openrouter`): run generation against any
  OpenRouter model with a single `OPENROUTER_API_KEY`, including free and
  low-cost ones. Structured output forces schema-honoring routing
  (`provider.require_parameters`), and the CLI surfaces a recommended-models
  note (Claude Opus 4.8 / GPT 5.5).
- Official MCP Registry metadata: `server.json`, a README `mcp-name` marker, and
  `docs/registry-publish.md` describing the publish flow.

### Changed

- `generate_json()` now uses Anthropic structured outputs (`messages.parse` with
  `output_format`) instead of `temperature=0` plus JSON extraction. `generate()`
  and `generate_stream()` forward `temperature` only for models that accept it
  (a version floor of Opus ≥ 4.7 plus the Fable/Mythos families), so the newest
  reasoning models (Opus 4.7+, Fable 5) work without a 400.

### Documentation

- README now leads with a hero GIF driven by `mcpforge demo` (deterministic, no
  API key) and documents the `demo` command and the OpenRouter provider.

## [0.3.2] - 2026-06-20

### Changed

- Bumped the `fastmcp` dependency floor from `>=3.2.3` to `>=3.4.2`, tracking the
  latest FastMCP 3.x release. Generated-server shape and the full example suite
  were re-validated against FastMCP 3.4.2.

### Fixed

- Removed a personal email address from the published package metadata
  (`[project.authors]` in `pyproject.toml`). PyPI metadata is immutable, so a new
  release was required to correct the public project page.

### Documentation

- Repositioned the README to lead with "one English sentence in, a tested,
  spec-free FastMCP 3.x server out", added a bring-your-own-key note with a
  clearly-estimated per-generation cost range, and fixed the dangling
  `demo-assets.md` link.
- Rendered and embedded the deterministic `run-and-test.gif` demo (drives the
  committed `examples/todo-server` fixture, no API key required) and added
  `demo-assets.md` with the demo shot list and per-asset sanitization checklist.

## [0.3.1] - 2026-06-18

### Security

- Upgraded `idna` (3.11 → 3.18) and `starlette` (1.0.0 → 1.2.1) in the locked
  dependency set, resolving GHSA-65pc-fj4g-8rjx (CVE-2026-45409) and
  GHSA-86qp-5c8j-p5mr (CVE-2026-48710).
- Upgraded `vitest` to `^4.1.0` in the TypeScript example fixtures, resolving
  GHSA-5xrq-8626-4rwp (CVE-2026-47429). Development-only dependency in the
  examples; not part of the published `fastmcp-builder` distribution.

### Documentation

- Rewrote the README into a 60-second quick start with PyPI, Python, and CI
  badges, a synthetic sample generated server, and copy-paste commands.
- Added a "Build, then audit" section pairing mcpforge with the companion
  `mcp-audit` (`mcp-permission-audit`) tool.
- Added reproducible [`vhs`](https://github.com/charmbracelet/vhs) demo tapes
  under `docs/assets/` (hero, run-and-test, build-then-audit) with pre-staged
  README embed slots, plus a `demo-assets.md` shot-list and `launch-posts.md`
  launch drafts.

## [0.3.0] - 2026-05-10

### Added

- Read-only generated-server inspection through `mcpforge inspect`.
- Local readiness diagnostics through `mcpforge doctor`.
- JSON output for status-oriented commands including `list`, `validate`, and `version`.
- MCP server parity for generation options, inspection, doctor checks, and server discovery.
- OpenAPI curation controls for tags, operations, limits, auth/env metadata, and method/path metadata.
- Generated `.env.example`, Python `fastmcp.json`, and TypeScript README/env scaffolding.
- Live generated fixture examples for REST API, filesystem, database, and TypeScript todo profiles.
- Provider abstraction with Anthropic stable and OpenAI explicitly gated until deterministic evidence exists.
- First-class prompt/resource model support and prompt/resource conformance checks.

### Changed

- Publish the Python distribution as `fastmcp-builder` while preserving the `mcpforge` import package and console commands.
- Hardened TypeScript validation so Vitest test counts come from the real test summary.
- Hardened nested template-injection checks across plan content.

## [0.2.0] - 2026-05-10

### Added

- FastMCP 3.x server generation from plain-English descriptions.
- Claude-powered code generation via the Anthropic API.
- Interactive CLI (`mcpforge`) with `generate`, `update`, `validate`, `list`, `init`, and `version` commands.
- MCP server mode (`mcpforge-server`) for IDE and agent integration.
- Jinja2-based template system for server scaffolding.
- YAML configuration support for generation parameters.
- Rich terminal output with progress indicators.
- Python and TypeScript generated-server examples.
- PyPI publishing workflow via GitHub Actions.

### Changed

- Centralized the default Anthropic model pin so the CLI, API client, and MCP server share one source of truth.
- Treat executed test failures as validation failures in CLI and MCP validation outputs.
- Updated generated-server guidance and bundled examples to use standard Python exceptions instead of string-based `McpError`.
- Aligned CI with the package's Python 3.12+ runtime requirement.

## [0.1.0] - 2024-12-01

### Added
- Initial project scaffold
- Basic FastMCP server generation prototype

[Unreleased]: https://github.com/saagpatel/mcpforge/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/saagpatel/mcpforge/releases/tag/v0.3.2
[0.3.1]: https://github.com/saagpatel/mcpforge/releases/tag/v0.3.1
[0.3.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.3.0
[0.2.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.2.0
[0.1.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.1.0
