# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes.

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

[Unreleased]: https://github.com/saagpatel/mcpforge/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.3.0
[0.2.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.2.0
[0.1.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.1.0
