# Demo assets

Recorded GIFs for the project README, plus the [`vhs`](https://github.com/charmbracelet/vhs)
tapes that produce them. Re-render any GIF when the CLI output changes — the tape
is the source of truth, the `.gif` is the build artifact.

See [`../../demo-assets.md`](../../demo-assets.md) for the full shot-list and the
per-asset sanitization checklist.

## Tapes

| Tape | Produces | README slot | Live API call? |
|------|----------|-------------|----------------|
| `hero.tape` | `hero.gif` | `## ⚡ 60-second start` (shot 1) | **No** — runs `mcpforge demo` (deterministic, no key) |
| `run-and-test.tape` | `run-and-test.gif` | 60-second start, run/test (shot 2) | No — deterministic |
| `build-then-audit.tape` | `build-then-audit.gif` | `## Build, then audit` (shot 4) | **Yes** — real `generate` |

`hero.tape` drives `mcpforge demo`, which uses a built-in cassette replay and
needs no API key and costs nothing. `run-and-test.tape` drives the committed
`examples/todo-server` fixture and is similarly deterministic. Only
`build-then-audit.tape` calls the real `mcpforge generate`, which makes a live
Anthropic API call (needs `ANTHROPIC_API_KEY` and network, and costs money per render).

## Install vhs

```bash
brew install vhs          # macOS
# or: go install github.com/charmbracelet/vhs@latest
```

## Render

```bash
# from the repo root
vhs docs/assets/hero.tape                  # deterministic, no key needed (mcpforge demo)
vhs docs/assets/run-and-test.tape          # deterministic, no key needed
export ANTHROPIC_API_KEY="your_real_key"   # only for the live tape below
vhs docs/assets/build-then-audit.tape
```

`build-then-audit.tape` calls a live LLM, so latency varies. If the GIF cuts off
before the green validation summary, increase the `Sleep` after the `generate`
line in that tape.

## Before committing a rendered GIF

- No username / hostname / absolute home path (`/Users/...`) in the prompt — the
  tapes set `PS1='$ '` and run in a temp dir to avoid this.
- No API key on screen (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `sk-…`, `ghp_…`).
- The generated-from description stays a synthetic toy (weather), never a real
  internal service.
- `build-then-audit.gif`: confirm `mcp-audit` output shows env-var *key names*
  only — never secret values.

## Embedding

Reference GIFs with **absolute** raw URLs so they render on both GitHub and PyPI.
PyPI does not rewrite relative paths — a `docs/assets/...` path renders on GitHub
but breaks on the PyPI project page:

```markdown
![mcpforge: one sentence to a running MCP server](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/hero.gif)
```
