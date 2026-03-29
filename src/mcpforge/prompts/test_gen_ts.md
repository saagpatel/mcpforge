# FastMCP TypeScript Test Generator

You are an expert TypeScript developer. Generate a Vitest test suite for an MCP server.

## Pattern

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { server } from "./server.js";

describe("tool_name", () => {
  it("returns expected result", async () => {
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test", version: "1.0" });
    await client.connect(clientTransport);
    const result = await client.callTool({ name: "tool_name", arguments: { param: "value" } });
    expect(result.content[0].text).toBe(JSON.stringify({ result: "value" }));
  });
});
```

## Rules
- Use Vitest (import from "vitest")
- Use InMemoryTransport for in-process testing
- Write at least 1 happy path test + 1 error case per tool
- Do NOT use markdown code fences in your output
- Generate ONE complete test_server.test.ts file
