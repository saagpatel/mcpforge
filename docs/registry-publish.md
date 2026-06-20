# Publishing to the official MCP Registry

mcpforge ships an MCP server (`mcpforge-server`, stdio transport), so it can be
listed in the [official MCP Registry](https://registry.modelcontextprotocol.io).
The registry hosts metadata only; the package itself lives on PyPI
(`fastmcp-builder`). Server name: `io.github.saagpatel/mcpforge`.

## One-time / per-release prerequisites

The registry verifies PyPI ownership by reading an `mcp-name` marker from the
**published package description** (which is the README at publish time). PyPI
descriptions are immutable per version, so the marker must be present in the
README of the release you point the registry at.

1. **README marker** (already added): the line
   `<!-- mcp-name: io.github.saagpatel/mcpforge -->` sits near the top of
   `README.md`. Keep it there.
2. **`server.json`** (in repo root): both the top-level `version` and
   `packages[0].version` must equal the **exact release version** you are
   publishing (they must match the PyPI version the registry resolves). Synced
   to `0.3.3` for this release; re-sync on every future release.
3. **Release**: cut and publish that version to PyPI as usual (the marker rides
   along in the description). Verify on PyPI before continuing.

## Publish step (operator-run; GitHub auth)

```bash
# Install the publisher CLI if needed (see modelcontextprotocol/registry releases).
mcp-publisher login github          # opens GitHub OAuth; namespace io.github.saagpatel
mcp-publisher publish               # reads ./server.json, verifies the PyPI marker
```

`login github` is interactive and authenticates the `io.github.saagpatel/*`
namespace, so it is operator-run, not agent-run.

## Other directories (no release dependency)

- **glama.ai** — auto-crawls the ecosystem and the awesome-mcp-servers list and
  generates score badges. Expected to auto-discover mcpforge after the
  awesome-mcp-servers entry merges; can be claimed later via glama's GitHub flow.
- **mcp.so** — community directory; submit the GitHub repo URL via the site.
  Confirm the current submit flow at submission time.
