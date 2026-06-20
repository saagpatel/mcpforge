# hero.tape — one command, a tested MCP server (README hero shot)
#
# Renders: docs/assets/hero.gif   (README "60-second start" hero, shot 1)
#
# Fully deterministic: `mcpforge demo` runs the real plan -> generate -> validate
# pipeline against a built-in recording. No Anthropic API key, no LLM call, no
# spend — renders identically every time (unlike a live `generate`, which costs
# money and varies in latency and output).
#
# Sanitization (see ../../demo-assets.md):
#   - PS1='$ ' so no user@host prompt.
#   - Runs from a clean /tmp dir so the result panel's output path never shows
#     the home dir (/Users/...).
#   - FASTMCP_CHECK_FOR_UPDATES=off silences FastMCP's update-nag banner.
#   - Hidden pre-warm runs the demo once (populating the uv cache) and discards
#     it, so the visible run is snappy instead of waiting on first-time installs.
#
# Render requirements:
#   - vhs        https://github.com/charmbracelet/vhs
#   - uv         https://docs.astral.sh/uv/
#   - mcpforge   on PATH — from the repo root: `uv tool install .`
#
# Render from the repo root:  vhs docs/assets/hero.tape

Require uv
Require mcpforge

Output docs/assets/hero.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 760
Set Theme "Dracula"
Set Padding 24
Set TypingSpeed 45ms

# --- setup, hidden: clean temp dir, silence the update banner, pre-warm the uv
#     cache by running the demo once and discarding it ---
Hide
Type "export PS1='$ '" Enter
Type "export FASTMCP_CHECK_FOR_UPDATES=off" Enter
Type "cd /tmp && rm -rf mcpforge-hero && mkdir mcpforge-hero && cd mcpforge-hero" Enter
Type "mcpforge demo -o .warmup --force >/dev/null 2>&1" Enter
Sleep 20s
Type "clear" Enter
Show

# --- one command: no key, no sentence — plan -> generate -> validate, all green ---
Type "mcpforge demo" Enter
Sleep 12s
