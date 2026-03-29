# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-01-01

### Added
- FastMCP 3.x server generation from plain-English descriptions
- Claude-powered code generation via the Anthropic API
- Interactive CLI (`mcpforge`) with `generate`, `validate`, and `serve` subcommands
- MCP server mode (`mcpforge-server`) for IDE and agent integration
- Jinja2-based template system for server scaffolding
- YAML configuration support for generation parameters
- Rich terminal output with progress indicators
- Comprehensive test suite (27 test files, pytest + pytest-asyncio)
- PyPI publishing workflow via GitHub Actions

## [0.1.0] - 2024-12-01

### Added
- Initial project scaffold
- Basic FastMCP server generation prototype

[Unreleased]: https://github.com/saagpatel/mcpforge/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/saagpatel/mcpforge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/saagpatel/mcpforge/releases/tag/v0.1.0
