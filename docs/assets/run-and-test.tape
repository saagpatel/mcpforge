# run-and-test.tape — a generated server: tests pass, then it runs
#
# Renders: docs/assets/run-and-test.gif   (README shot 2)
#
# Fully deterministic: drives the committed examples/todo-server fixture.
# No Anthropic API key, no LLM call — renders identically every time.
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

# --- setup, hidden: enter the fixture and warm the venv ---
Hide
Type "export PS1='$ '" Enter
Type "cd examples/todo-server" Enter
Type "uv sync >/dev/null 2>&1" Enter
Sleep 6s
Type "clear" Enter
Show

# --- the generated pytest suite passes ---
Type "uv run pytest -v" Enter
Sleep 8s

# --- and the server boots on streamable-http ---
Type "uv run server.py" Enter
Sleep 4s
Ctrl+C
Sleep 1s
