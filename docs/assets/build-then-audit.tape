# build-then-audit.tape — forge a server, then audit your MCP surface
#
# Renders: docs/assets/build-then-audit.gif   (README "Build, then audit", shot 4)
#
# Render requirements:
#   - vhs                 https://github.com/charmbracelet/vhs
#   - mcpforge            uv tool install fastmcp-builder
#   - uv                  https://docs.astral.sh/uv/   (provides uvx for mcp-audit)
#   - ANTHROPIC_API_KEY   exported in THIS shell  (a REAL key — never commit it)
#   - network access      the `generate` step makes a real Anthropic API call
#
# Render:  vhs docs/assets/build-then-audit.tape
#
# NOTE: bump `Sleep 30s` if generation is slower than the recording window.

Require mcpforge
Require uv

Output docs/assets/build-then-audit.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 820
Set Theme "Dracula"
Set Padding 24
Set TypingSpeed 45ms

Hide
Type "export PS1='$ '" Enter
Type "cd $(mktemp -d)" Enter
Type "rm -rf weather-server" Enter
Type "clear" Enter
Show

# --- build: forge a server from one sentence ---
Type `mcpforge generate "A weather server that returns today's forecast for a city" -o weather-server`
Sleep 800ms
Enter
Sleep 30s

# --- audit: scan everything your agents can reach (read-only, no install) ---
Type "uvx --from mcp-audits mcp-audit scan --ssrf-check" Enter
Sleep 12s
Sleep 2s
