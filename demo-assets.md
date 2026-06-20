# Demo assets — shot list & sanitization checklist

The README embeds a small set of recorded terminal GIFs. Each GIF is a build
artifact; its [`vhs`](https://github.com/charmbracelet/vhs) tape under
[`docs/assets/`](docs/assets/) is the source of truth. Re-render a GIF whenever
the CLI output it captures changes.

See [`docs/assets/README.md`](docs/assets/README.md) for install/render commands.

## Shot list

| # | Tape | GIF | README slot | Live API call? |
|---|------|-----|-------------|----------------|
| 1 | `docs/assets/hero.tape` | `hero.gif` | `## ⚡ 60-second start` (lead) | **Yes** — real `generate` (needs `ANTHROPIC_API_KEY`, costs money) |
| 2 | `docs/assets/run-and-test.tape` | `run-and-test.gif` | 60-second start, run/test | **No** — deterministic, drives the committed `examples/todo-server` fixture |
| 4 | `docs/assets/build-then-audit.tape` | `build-then-audit.gif` | `## Build, then audit` | **Yes** — real `generate` + `mcp-audit` |

Only shot 2 (`run-and-test.gif`) is rendered and embedded by default — it needs
no key and reproduces identically every time. Shots 1 and 4 call the live model,
so their embeds stay commented in the README until rendered with a real key.

## Per-asset sanitization checklist

Run through this before committing any rendered GIF:

- [ ] **No home path.** No `/Users/...`, username, or hostname on screen. The
      tapes set `PS1='$ '` and `run-and-test.tape` copies the fixture to
      `/tmp/todo-server` with a freshly built `.venv`, so `pytest`'s absolute
      `python:`/`rootdir:` lines resolve under `/tmp`, never the home dir.
- [ ] **No secrets.** No `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` values, and no
      `sk-…` / `ghp_…` tokens visible. The live tapes export the key in a hidden
      (`Hide`) block.
- [ ] **No update-nag.** `run-and-test.tape` exports
      `FASTMCP_CHECK_FOR_UPDATES=off` so FastMCP's "update available" banner stays
      out of the frame.
- [ ] **Clean ending.** No Ctrl+C traceback. `run-and-test.tape` ends on the
      server's startup banner — SIGTERM teardown at end-of-tape is clean, SIGINT
      is not.
- [ ] **Toy subject only.** The generated-from description stays a synthetic toy
      (weather / todo), never a real internal service.
- [ ] **`build-then-audit.gif` only:** confirm `mcp-audit` output shows env-var
      *key names*, never values.

## Embedding

Reference GIFs with **absolute** raw URLs so they render on both GitHub and PyPI
(PyPI does not rewrite relative `docs/assets/...` paths):

```markdown
![alt text](https://raw.githubusercontent.com/saagpatel/mcpforge/main/docs/assets/run-and-test.gif)
```
