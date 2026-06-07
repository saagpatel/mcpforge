# hero.tape — mcpforge: one sentence -> a tested, runnable MCP server
#
# Renders: docs/assets/hero.gif   (README "60-second start" hero, shot 1)
#
# Render requirements:
#   - vhs                 https://github.com/charmbracelet/vhs
#   - mcpforge            uv tool install fastmcp-builder
#   - uv                  https://docs.astral.sh/uv/
#   - ANTHROPIC_API_KEY   exported in THIS shell  (a REAL key — never commit it)
#   - network access      `generate` makes a real Anthropic API call (costs money)
#
# Render:  vhs docs/assets/hero.tape
#
# NOTE: generation latency varies (it calls an LLM). If the GIF cuts off before
# the green validation summary appears, increase the `Sleep 30s` below.

Require mcpforge

Output docs/assets/hero.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 760
Set Theme "Dracula"
Set Padding 24
Set TypingSpeed 45ms

# --- leak-free setup, hidden from the recording ---
Hide
Type "export PS1='$ '" Enter
Type "cd $(mktemp -d)" Enter
Type "rm -rf weather-server" Enter
Type "clear" Enter
Show

# --- the whole loop: one sentence in ---
Type `mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server`
Sleep 800ms
Enter

# plan -> generate -> validate (syntax / security / lint / import / pytest)
Sleep 30s

# --- prove it's a complete, real project that runs ---
Type "ls weather-server" Enter
Sleep 2s
Type "uv run --directory weather-server pytest -q" Enter
Sleep 12s
Sleep 2s
