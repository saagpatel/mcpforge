# FastMCP TypeScript Test Generator

You are an expert TypeScript developer. Generate a Vitest test suite for an MCP server.

## Pattern

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { server } from "./server.js";

type TextContent = { type: "text"; text: string };

function textContent(result: Awaited<ReturnType<Client["callTool"]>>, index = 0): TextContent {
  const content = result.content as TextContent[];
  return content[index];
}

describe("tool_name", () => {
  it("returns expected result", async () => {
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test", version: "1.0" });
    await client.connect(clientTransport);
    const result = await client.callTool({ name: "tool_name", arguments: { param: "value" } });
    expect(textContent(result).text).toBe(JSON.stringify({ result: "value" }));
  });
});
```

## Rules
- Use Vitest (import from "vitest")
- Use InMemoryTransport for in-process testing
- Write at least 1 happy path test + 1 error case per tool
- Treat `client.callTool()` result content as `unknown`: define a local helper or type
  assertion before accessing `content[0].text`, `content[0].type`, or content length
- Do not access `result.content[...]` directly in assertions; use the typed helper
- Do NOT use markdown code fences in your output
- Generate ONE complete `server.test.ts` file
