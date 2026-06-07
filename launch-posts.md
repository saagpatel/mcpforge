# Launch posts — mcpforge

Draft copy for launching mcpforge publicly. Framed for developers adopting MCP.
Edit voice/links before posting. Repo: https://github.com/saagpatel/mcpforge ·
PyPI: https://pypi.org/project/fastmcp-builder/

---

## Show HN (news.ycombinator.com)

**Title:**
Show HN: mcpforge – Generate a complete, tested MCP server from one sentence

**URL:** https://github.com/saagpatel/mcpforge

**Body (first comment):**

I kept writing the same MCP server boilerplate by hand — FastMCP setup, tool
signatures, input validation, error handling, a test file, the client config —
before I could get to the one tool I actually wanted. mcpforge collapses that
into a sentence.

    uv tool install fastmcp-builder
    export ANTHROPIC_API_KEY="..."
    mcpforge generate "A weather server that returns today's forecast for a city"

You get a complete project, not a snippet: `server.py` (FastMCP 3.x), a real
pytest suite, `pyproject.toml`, a README, and an MCP client `config.json`.

The part I cared most about is that it doesn't just dump LLM output and wish you
luck. Generation is three stages — it asks Claude for a structured JSON plan
(tool names, signatures, descriptions), validates that plan against a Pydantic
model, renders it through Jinja2 templates, then runs the result through syntax
checks, a security scan, ruff, an import check, and pytest. If validation fails
it self-heals once before handing it back. So what lands on disk has already been
run.

A few other things it does: `mcpforge update ./srv "add a CSV export tool"` for
targeted edits (with backups), `--from-openapi spec.yaml` to turn a REST spec
into a curated MCP server, `--language typescript`, and an MCP server mode
(`mcpforge-server`) so an AI assistant can generate and validate servers as
tools.

It has a sibling, mcp-audit (`uvx --from mcp-permission-audit mcp-audit scan`),
which scans every MCP server already wired into your machine and risk-scores what
each one can touch. The pitch for the pair is simple: forge a server, then audit
your whole MCP surface before you trust it in an agent.

Stack: Python 3.12+, FastMCP 3.x, Anthropic SDK (OpenAI provider is gated behind
hosted smokes for now), Click, Pydantic v2. MIT licensed, v0.3 — early but the
generate → validate → run loop works end to end today.

Happy to answer questions, and genuinely want to hear where the generated output
falls short of what you'd hand-write.

---

## r/mcp (and r/LocalLLaMA / r/ClaudeAI)

**Title:**
mcpforge: describe an MCP server in one sentence, get a tested FastMCP 3.x one back

**Body:**

I built mcpforge to kill the boilerplate gap between "I want an MCP server that
does X" and actually having one running.

```bash
uv tool install fastmcp-builder
export ANTHROPIC_API_KEY="..."
mcpforge generate "A weather server that returns today's forecast for a city"
```

That produces a full project — `server.py` on FastMCP 3.x, a pytest suite,
`pyproject.toml`, a README, and an MCP client `config.json` — ready to
`uv run server.py`.

What makes it more than a prompt wrapper:

- **Plan → generate → validate.** It extracts a structured tool plan first
  (validated against a Pydantic model), then renders templates, then runs the
  output through syntax / security / lint / import / pytest checks. One self-heal
  retry on failure. The server you get has already been executed.
- **Iterate safely.** `mcpforge update ./srv "add a tool to export as CSV"`
  makes targeted changes and backs up anything it touches.
- **OpenAPI in.** `--from-openapi spec.yaml` with tag/operation filters to keep
  the generated surface focused.
- **TypeScript or Python**, and an MCP server mode so assistants can call it as a
  tool.

It pairs with **mcp-audit** (`mcp-permission-audit` on PyPI), which scans the MCP
servers already configured on your machine and tells you what each can actually
reach — read-only, env-var key names only, never values. Build with mcpforge,
audit with mcp-audit.

It's v0.3 and MIT licensed. Repo: https://github.com/saagpatel/mcpforge

Would love feedback from people actually shipping MCP servers — especially where
the generated code doesn't match what you'd write by hand.

---

## LinkedIn

The friction in adopting MCP isn't the protocol — it's everything around the one
tool you actually want to expose. FastMCP setup, tool signatures, input
validation, error handling, a test file, the client config. By the time you're
done, the interesting 20 lines are buried under boilerplate.

So I built mcpforge. You describe the server in plain English; it generates a
complete, tested MCP server:

  mcpforge generate "A weather server that returns today's forecast for a city"

What you get back isn't a snippet — it's a full project: a FastMCP 3.x server, a
real pytest suite, packaging, a README, and an MCP client config. And it isn't
raw LLM output, either. mcpforge plans the tools as structured data, validates
that plan, renders it through templates, then runs the result through syntax,
security, lint, import, and pytest checks before it ever reaches you. If
something fails, it self-heals once. The code that lands on disk has already
been run.

It has a sibling I'm just as excited about: mcp-audit, which scans every MCP
server already wired into your environment and risk-scores what each one can
touch — read-only, surfacing env-var key names only, never values.

Together they're a workflow, not two tools: forge a server, then audit your MCP
surface before you trust it inside an agent. Build, then verify your blast
radius.

Both are open source (MIT) and on PyPI. mcpforge: pip/uv install
`fastmcp-builder`. If you're building on MCP, I'd love your feedback — and your
worst-case test descriptions.

#MCP #ModelContextProtocol #AI #DeveloperTools #OpenSource #Python
