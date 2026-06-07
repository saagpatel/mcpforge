# Demo assets to record — mcpforge

A shot-list of GIFs/screenshots to capture for the README and launch posts.
**These must be recorded from a real terminal — do not fabricate or hand-edit
output.** Record against a freshly generated synthetic server (the "weather"
toy from the README, or any `examples/` server) so nothing real leaks.

## Capture setup (recommended)

- Terminal: ~100 cols × ~30 rows, large readable font, high-contrast theme.
- Tooling: [`vhs`](https://github.com/charmbracelet/vhs) for reproducible,
  scriptable GIFs (preferred — re-renders cleanly on every change), or
  `asciinema` + `agg` for lighter-weight casts.
- Keep each GIF under ~8–12s and loop it; trim dead air and API latency.
- **Before recording:** clear scrollback, and confirm the shell prompt shows no
  username, hostname, absolute home path, or API key. Use a clean demo prompt
  (e.g. `PS1='$ '`).

## Shots

### 1. Hero — one sentence → running server  ⭐ (top of README)
The headline GIF. Show the full loop in one take:
```
mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server
```
Capture the plan spinner, the generation, and the green validation summary
(syntax / security / lint / import / pytest passing). End on the created file
tree. **Embed:** directly under the `## ⚡ 60-second start` heading. **Reuse:**
Show HN / r/mcp / LinkedIn.

### 2. Run + test the generated server
```
cd weather-server
uv run pytest -v
uv run server.py
```
Show the generated pytest suite passing, then the server booting on
streamable-http. Proves "already validated, actually runs." **Embed:** after the
run-commands block in the 60-second start.

### 3. Iterate safely — `mcpforge update`
```
mcpforge update ./weather-server "Add a tool to return a 3-day forecast"
```
Show the targeted diff, the backup notice, and re-validation. **Embed:** near the
"Iterate safely" feature bullet. **Reuse:** launch posts (the "not a prompt
wrapper" point).

### 4. Build → audit, the toolkit pair  ⭐
Two-command story for the sibling-tool narrative:
```
mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server
uvx --from mcp-permission-audit mcp-audit scan --ssrf-check
```
Show forging a server, then mcp-audit's risk-scored table of the local MCP
surface. **Embed:** under `## Build, then audit — the MCP toolkit`. **Reuse:**
all three launch posts — this is the differentiator.

### 5. OpenAPI → curated MCP server
```
mcpforge generate --from-openapi petstore.yaml --openapi-include-tag pet --openapi-limit 5
```
Use a public sample spec (e.g. the Swagger Petstore) — **never an internal/real
API spec.** Shows the spec-to-server path with curation. **Embed:** OpenAPI
feature area. Optional for v1 launch.

### 6. `mcpforge doctor` — readiness check
```
mcpforge doctor
```
Quick static screenshot (not a GIF) of the environment/provider readiness output.
Good for the "More commands" section and for onboarding clarity.

## Stills (screenshots, not GIFs)

- `examples/` directory tree of a generated project (server.py, test_server.py,
  pyproject.toml, README.md, config.json) — shows "complete project, not a
  snippet."
- The green validation summary panel on its own (crop from shot 1) — strong
  inline thumbnail.

## Where files should live

Save recorded assets under `docs/assets/` (e.g. `docs/assets/hero.gif`) and
reference them with relative paths in `README.md`.

Reproducible [`vhs`](https://github.com/charmbracelet/vhs) tapes already exist for
shots 1, 2, and 4 — see [`docs/assets/`](docs/assets/) and its
[`README.md`](docs/assets/README.md) for render instructions:

- `docs/assets/hero.tape` → `hero.gif` (shot 1, live `generate`)
- `docs/assets/run-and-test.tape` → `run-and-test.gif` (shot 2, deterministic — no API key)
- `docs/assets/build-then-audit.tape` → `build-then-audit.gif` (shot 4, live `generate` + `mcp-audit`)

Add a tape for any new GIF so the demos can be re-rendered when the CLI output
changes.

## Pre-publish sanitization checklist (per asset)

- [ ] No username / hostname / absolute home path (`/Users/...`) in the prompt.
- [ ] No API key visible (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `sk-…`, `ghp_…`).
- [ ] Generated-from description is a synthetic toy, not a real internal service.
- [ ] No real internal hostnames, endpoints, or employer references on screen.
- [ ] mcp-audit output (shot 4) shows key *names* only — no secret values.
