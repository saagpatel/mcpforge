# Codex Playbook For mcpforge

## Default Mode

Use Codex App Projects for Python generator, MCP server, validation, and documentation work.

Use a Worktree before changing any of these surfaces:

- generated templates under `src/mcpforge/templates/`
- default model or provider behavior
- prompt contracts under `src/mcpforge/prompts/`
- package/security validation behavior
- generated example server fixtures

## Verification Baseline

For generator or MCP behavior changes, collect evidence from the smallest relevant set:

- `uv run pytest`
- `uv run ruff check .`
- generated-server fixture checks
- focused CLI smoke output for `generate`, `inspect`, `extend`, or `validate` when touched

For provider/model changes, include evidence that structured JSON generation and validation still behave deterministically.

## Guardrails

- Do not hardcode API keys in generated server code; use environment variables.
- Do not skip the structured planning stage before generation.
- Do not trust LLM output without validation.
- Do not migrate default models or provider behavior without explicit evidence.
- Preserve existing local work unless the user explicitly asks to change it.
