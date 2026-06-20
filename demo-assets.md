# Demo assets — shot list & sanitization guide

The README embeds a small set of recorded terminal GIFs. Each GIF is a build
artifact; its [`vhs`](https://github.com/charmbracelet/vhs) tape under
[`docs/assets/`](docs/assets/) is the source of truth. Re-render a GIF whenever
the CLI output it captures changes.

See [`docs/assets/README.md`](docs/assets/README.md) for install/render commands.

## Shot list

| # | Tape | GIF | README slot | Live API call? |
|---|------|-----|-------------|----------------|
| 1 | `docs/assets/hero.tape` | `hero.gif` | `## ⚡ 60-second start` (lead) | **No** — runs `mcpforge demo` (deterministic, no key, no cost) |
| 2 | `docs/assets/run-and-test.tape` | `run-and-test.gif` | 60-second start, run/test | **No** — deterministic, drives the committed `examples/todo-server` fixture |
| 4 | `docs/assets/build-then-audit.tape` | `build-then-audit.gif` | `## Build, then audit` | **Yes** — real `generate` + `mcp-audit` |

Shots 1 and 2 are fully deterministic and need no API key. Only shot 4
(`build-then-audit.gif`) calls the live model and requires `ANTHROPIC_API_KEY`.

## Per-asset sanitization guide

Before committing any rendered GIF, verify the following:

**No home path.** No `/Users/...`, username, or hostname should appear on screen.
The tapes set `PS1='$ '` and `run-and-test.tape` copies the fixture to
`/tmp/todo-server` with a freshly built `.venv`, so `pytest`'s absolute
`python:`/`rootdir:` lines resolve under `/tmp`, never the home directory.

**No secrets.** No `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` values, and no
`sk-…` or `ghp_…` tokens should be visible. The live tapes export keys in a
hidden (`Hide`) block.

**No update-nag.** `run-and-test.tape` exports `FASTMCP_CHECK_FOR_UPDATES=off`
so FastMCP's "update available" banner stays out of the frame.

**Clean ending.** No Ctrl+C traceback. `run-and-test.tape` ends on the server's
startup banner — SIGTERM teardown at end-of-tape is clean, SIGINT is not.

**Toy subject only.** The generated-from description stays a synthetic toy
(weather / todo), never a real internal service.

**`build-then-audit.gif` only:** confirm `mcp-audit` output shows env-var
key names only, never values.

## Embedding

Reference GIFs with **absolute** raw URLs so they render on both GitHub and PyPI
(PyPI does not rewrite relative `docs/assets/...` paths):

```markdown
![alt text](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/run-and-test.gif)
```
