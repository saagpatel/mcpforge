# run-and-test.tape — a generated server: tests pass, then it runs
#
# Renders: docs/assets/run-and-test.gif   (README shot 2)
#
# Fully deterministic: drives the committed examples/todo-server fixture.
# No Anthropic API key, no LLM call — renders identically every time.
#
# Sanitization (see ../../demo-assets.md):
#   - PS1='$ ' so no user@host prompt.
#   - Runs from a copy in /tmp so pytest's absolute paths never show the
#     home dir (/Users/...).
#   - FASTMCP_CHECK_FOR_UPDATES=off silences FastMCP's update-nag banner.
#   - Ends on the server's startup banner (SIGTERM teardown is clean, so no
#     Ctrl+C traceback).
#
# Render requirements:
#   - vhs   https://github.com/charmbracelet/vhs
#   - uv    https://docs.astral.sh/uv/
#
# Render from the repo root:  vhs docs/assets/run-and-test.tape

Require uv

Output docs/assets/run-and-test.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 760
Set Theme "Dracula"
Set Padding 24
Set TypingSpeed 45ms

# --- setup, hidden: copy the fixture to a clean temp dir (keeps the home
#     path out of pytest output), silence the update banner, warm the venv ---
Hide
Type "export PS1='$ '" Enter
Type "export FASTMCP_CHECK_FOR_UPDATES=off" Enter
Type "rm -rf /tmp/todo-server && cp -R examples/todo-server /tmp/todo-server && cd /tmp/todo-server && rm -rf .venv" Enter
Type "uv sync >/dev/null 2>&1" Enter
Sleep 12s
Type "clear" Enter
Show

# --- the generated pytest suite passes ---
Type "uv run pytest -v" Enter
Sleep 8s

# --- and the server boots on streamable-http (clean banner, no Ctrl+C noise) ---
Type "uv run server.py" Enter
Sleep 5s
