# mcpforge Provider Matrix

Last updated: 2026-06-20

This runbook separates local release readiness from hosted provider readiness. It
is intentionally safe to use in a local audit: do not read provider keys, do not
print secrets, and do not run hosted smokes unless the operator has explicitly
approved the paid provider calls.

## Current Gate Summary

| Lane | Status | Evidence | Decision Needed |
| --- | --- | --- | --- |
| Local package and validation | Green | `fastmcp-builder==0.3.2` is published, `mcpforge version` reports `0.3.2`, and the safe local verification commands below are the live validation baseline. | None for local-only work. |
| Anthropic hosted Python generation | Blocked | The hosted smoke exists and requires `MCPFORGE_RUN_HOSTED_SMOKE=1` plus `ANTHROPIC_API_KEY`. The latest provider retry was blocked by Anthropic low credit before generation. | Replenish Anthropic credit and approve the hosted smoke. |
| Anthropic hosted TypeScript generation | Blocked | The hosted TypeScript smoke exists and requires `MCPFORGE_RUN_HOSTED_TS_SMOKE=1` plus `ANTHROPIC_API_KEY`. The latest provider retry was blocked by Anthropic low credit before generation. | Replenish Anthropic credit and approve the hosted smoke. |
| Anthropic hosted authenticated OpenAPI generation | Blocked | The hosted OpenAPI smoke exists and requires `MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1` plus `ANTHROPIC_API_KEY`. The latest provider retry was blocked by Anthropic low credit before generation. | Replenish Anthropic credit and approve the hosted smoke. |
| OpenAI structured output | Gated | The hosted structured-output smoke exists and requires `MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1` plus `OPENAI_API_KEY`. `OpenAIClient.generate_json` is implemented. | Provide `OPENAI_API_KEY` and approve the hosted smoke. |
| OpenAI planning | Gated | The hosted planning smoke exists and requires `MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1` plus `OPENAI_API_KEY`. | Provide `OPENAI_API_KEY` and approve the hosted smoke. |
| OpenAI generation | Gated | `src/mcpforge/providers.py` keeps OpenAI generation behind `MCPFORGE_ENABLE_OPENAI_PROVIDER=1`. The hosted generation smoke requires that flag plus `MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1` and `OPENAI_API_KEY`. | Provide `OPENAI_API_KEY`, approve the hosted smoke, and keep generation explicitly gated during testing. |
| OpenRouter (bring-your-own) | Bring-your-own | `OpenRouterClient` is enabled whenever `OPENROUTER_API_KEY` is set (not flag-gated). Three opt-in smokes prove the real path: `MCPFORGE_RUN_HOSTED_OPENROUTER_SMOKE` (structured output), `..._PLANNING_SMOKE` (ServerPlan), and `..._GENERATION_SMOKE` (full generate). Model defaults to `openai/gpt-5-mini`; override with `MCPFORGE_OPENROUTER_SMOKE_MODEL`. | Provide `OPENROUTER_API_KEY` and run the smokes against any model (free included) to confirm. |

## Provider Defaults

- Default provider: `anthropic`.
- Anthropic status: `stable`.
- OpenAI status: `gated`.
- OpenRouter status: `bring-your-own` (enabled with `OPENROUTER_API_KEY`; any
  model id via `--model`, default `anthropic/claude-opus-4.8`).
- `mcpforge doctor` reports local prerequisites, provider capabilities, and
  whether key environment variables are present. It does not prove provider
  credit, hosted API reachability, or generation quality.
- OpenAI must stay gated until the OpenAI structured-output, planning, and
  generation smokes pass repeatedly with a real key and the Anthropic release
  matrix is green again.

## Safe Local Verification

These commands do not read keys and should leave hosted smoke gates disabled:

```bash
env -u ANTHROPIC_API_KEY \
  -u OPENAI_API_KEY \
  -u MCPFORGE_RUN_HOSTED_SMOKE \
  -u MCPFORGE_RUN_HOSTED_TS_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE \
  -u MCPFORGE_ENABLE_OPENAI_PROVIDER \
  uv run ruff check .

env -u ANTHROPIC_API_KEY \
  -u OPENAI_API_KEY \
  -u MCPFORGE_RUN_HOSTED_SMOKE \
  -u MCPFORGE_RUN_HOSTED_TS_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE \
  -u MCPFORGE_ENABLE_OPENAI_PROVIDER \
  uv run ruff format --check .

env -u ANTHROPIC_API_KEY \
  -u OPENAI_API_KEY \
  -u MCPFORGE_RUN_HOSTED_SMOKE \
  -u MCPFORGE_RUN_HOSTED_TS_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE \
  -u MCPFORGE_ENABLE_OPENAI_PROVIDER \
  uv run pytest -q -p no:cacheprovider

env -u ANTHROPIC_API_KEY \
  -u OPENAI_API_KEY \
  -u MCPFORGE_RUN_HOSTED_SMOKE \
  -u MCPFORGE_RUN_HOSTED_TS_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE \
  -u MCPFORGE_ENABLE_OPENAI_PROVIDER \
  uv run mcpforge validate examples/todo-server

env -u ANTHROPIC_API_KEY \
  -u OPENAI_API_KEY \
  -u MCPFORGE_RUN_HOSTED_SMOKE \
  -u MCPFORGE_RUN_HOSTED_TS_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE \
  -u MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE \
  -u MCPFORGE_ENABLE_OPENAI_PROVIDER \
  uv run mcpforge validate examples/v03-authenticated-openapi-server
```

Optional package verification:

```bash
uv build --out-dir /tmp/mcpforge-dist-check --clear
scripts/verify_clean_install.sh
uvx --from fastmcp-builder==0.3.2 mcpforge version --json
```

## Approval-Required Hosted Smokes

Run these only after explicit approval for the paid hosted calls. Use real keys
from the execution environment; never paste or print key values in logs or docs.

```bash
MCPFORGE_RUN_HOSTED_SMOKE=1 \
  ANTHROPIC_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_echo_server

MCPFORGE_RUN_HOSTED_TS_SMOKE=1 \
  ANTHROPIC_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_typescript_echo_server

MCPFORGE_RUN_HOSTED_OPENAPI_SMOKE=1 \
  ANTHROPIC_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_generate_openapi_auth_server

MCPFORGE_RUN_HOSTED_OPENAI_SMOKE=1 \
  OPENAI_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_structured_output_smoke

MCPFORGE_RUN_HOSTED_OPENAI_PLANNING_SMOKE=1 \
  OPENAI_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_planning_smoke

MCPFORGE_RUN_HOSTED_OPENAI_GENERATION_SMOKE=1 \
  MCPFORGE_ENABLE_OPENAI_PROVIDER=1 \
  OPENAI_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openai_generate_echo_server

# OpenRouter (bring-your-own). Set MCPFORGE_OPENROUTER_SMOKE_MODEL to any model
# id — including free ones — to control cost; defaults to openai/gpt-5-mini.
MCPFORGE_RUN_HOSTED_OPENROUTER_SMOKE=1 \
  OPENROUTER_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openrouter_structured_output_smoke

MCPFORGE_RUN_HOSTED_OPENROUTER_PLANNING_SMOKE=1 \
  OPENROUTER_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openrouter_planning_smoke

MCPFORGE_RUN_HOSTED_OPENROUTER_GENERATION_SMOKE=1 \
  OPENROUTER_API_KEY=... \
  uv run pytest tests/test_hosted_generation_smoke.py::test_hosted_openrouter_generate_echo_server
```

## Release Decision Rule

- Local-only release posture is green when lint, formatting, unit tests,
  generated fixture validation, package build, and clean install checks pass.
- Provider-matrix release posture is not green while Anthropic hosted smokes are
  blocked by credit and OpenAI smokes are skipped for missing `OPENAI_API_KEY`.
- Publish patch releases only when the change does not depend on hosted provider
  behavior, and record that hosted provider smokes were intentionally not run.
- Park OpenAI ungating until OpenAI hosted smokes pass repeatedly and the
  Anthropic hosted matrix is green again.
