import { describe, it, expect, beforeEach } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { randomUUID } from "crypto";

// ── Replicate the in-memory store and server locally for testing ─────────────

interface TodoItem {
  id: string;
  title: string;
  priority: "low" | "medium" | "high";
  tags: string[];
  completed: boolean;
  createdAt: string;
  completedAt: string | null;
}

type Priority = "low" | "medium" | "high";
const VALID_PRIORITIES = ["low", "medium", "high"] as const;
const MAX_TITLE_LENGTH = 500;

function isValidPriority(p: string): p is Priority {
  return (VALID_PRIORITIES as readonly string[]).includes(p);
}

function isValidUUID(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}

function buildTestServer(todos: Map<string, TodoItem>) {
  function buildSummary() {
    const all = Array.from(todos.values());
    const completed = all.filter((t) => t.completed);
    const pending = all.filter((t) => !t.completed);
    const byPriority = (items: TodoItem[]) => ({
      low: items.filter((t) => t.priority === "low").length,
      medium: items.filter((t) => t.priority === "medium").length,
      high: items.filter((t) => t.priority === "high").length,
    });
    return {
      total: all.length,
      completed: completed.length,
      pending: pending.length,
      byPriority: {
        all: byPriority(all),
        pending: byPriority(pending),
        completed: byPriority(completed),
      },
    };
  }

  const s = new McpServer({ name: "TypeScript Todo Workflow", version: "0.1.0" });

  s.tool(
    "add_todo",
    "Add a new todo item with a title and optional priority and tags.",
    {
      title: z.string(),
      priority: z.enum(["low", "medium", "high"]).optional().default("medium"),
      tags: z.array(z.string()).optional(),
    },
    async ({ title, priority, tags }) => {
      const trimmedTitle = title.trim();
      if (!trimmedTitle) throw new Error("Title must not be empty.");
      if (trimmedTitle.length > MAX_TITLE_LENGTH)
        throw new Error(`Title exceeds maximum length of ${MAX_TITLE_LENGTH} characters.`);
      const resolvedPriority: Priority = priority ?? "medium";
      if (!isValidPriority(resolvedPriority))
        throw new Error(`Invalid priority value "${resolvedPriority}".`);
      const sanitizedTags = (tags ?? []).map((t) => t.trim()).filter(Boolean);
      const todo: TodoItem = {
        id: randomUUID(),
        title: trimmedTitle,
        priority: resolvedPriority,
        tags: sanitizedTags,
        completed: false,
        createdAt: new Date().toISOString(),
        completedAt: null,
      };
      todos.set(todo.id, todo);
      return { content: [{ type: "text" as const, text: JSON.stringify({ success: true, todo }) }] };
    }
  );

  s.tool(
    "list_todos",
    "List all todo items.",
    {
      completed: z.boolean().optional(),
      priority: z.enum(["low", "medium", "high"]).optional(),
      tag: z.string().optional(),
    },
    async ({ completed, priority, tag }) => {
      if (priority !== undefined && !isValidPriority(priority))
        throw new Error(`Invalid priority value "${priority}".`);
      let results = Array.from(todos.values());
      if (completed !== undefined) results = results.filter((t) => t.completed === completed);
      if (priority !== undefined) results = results.filter((t) => t.priority === priority);
      if (tag !== undefined) {
        const normalizedTag = tag.trim().toLowerCase();
        results = results.filter((t) => t.tags.some((tg) => tg.toLowerCase() === normalizedTag));
      }
      results.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      return {
        content: [
          { type: "text" as const, text: JSON.stringify({ success: true, count: results.length, todos: results }) },
        ],
      };
    }
  );

  s.tool(
    "get_todo",
    "Retrieve a single todo item by its unique ID.",
    { todo_id: z.string() },
    async ({ todo_id }) => {
      if (!isValidUUID(todo_id)) throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
      const todo = todos.get(todo_id);
      if (!todo) throw new Error(`Todo with ID "${todo_id}" not found.`);
      return { content: [{ type: "text" as const, text: JSON.stringify({ success: true, todo }) }] };
    }
  );

  s.tool(
    "complete_todo",
    "Mark a todo item as completed.",
    { todo_id: z.string() },
    async ({ todo_id }) => {
      if (!isValidUUID(todo_id)) throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
      const todo = todos.get(todo_id);
      if (!todo) throw new Error(`Todo with ID "${todo_id}" not found.`);
      if (todo.completed) throw new Error(`Todo with ID "${todo_id}" is already completed.`);
      todo.completed = true;
      todo.completedAt = new Date().toISOString();
      todos.set(todo_id, todo);
      return { content: [{ type: "text" as const, text: JSON.stringify({ success: true, todo }) }] };
    }
  );

  s.tool(
    "delete_todo",
    "Delete a todo item by its unique ID.",
    { todo_id: z.string() },
    async ({ todo_id }) => {
      if (!isValidUUID(todo_id)) throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
      const todo = todos.get(todo_id);
      if (!todo) throw new Error(`Todo with ID "${todo_id}" not found.`);
      todos.delete(todo_id);
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({
              success: true,
              message: `Todo "${todo.title}" (ID: ${todo_id}) deleted successfully.`,
              deleted: todo,
            }),
          },
        ],
      };
    }
  );

  s.tool("summarize_workload", "Return a structured summary.", {}, async () => {
    const summary = buildSummary();
    return { content: [{ type: "text" as const, text: JSON.stringify({ success: true, summary }) }] };
  });

  return s;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

type TextContent = { type: "text"; text: string };

function textContent(
  result: Awaited<ReturnType<Client["callTool"]>>,
  index = 0
): TextContent {
  const content = result.content as TextContent[];
  return content[index];
}

function parsedContent(result: Awaited<ReturnType<Client["callTool"]>>, index = 0): unknown {
  return JSON.parse(textContent(result, index).text);
}

async function makeClient(todos: Map<string, TodoItem>): Promise<Client> {
  const s = buildTestServer(todos);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await s.connect(serverTransport);
  const client = new Client({ name: "test", version: "1.0" });
  await client.connect(clientTransport);
  return client;
}

// ── add_todo ─────────────────────────────────────────────────────────────────

describe("add_todo", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("adds a todo with only a title (defaults to medium priority)", async () => {
    const result = await client.callTool({ name: "add_todo", arguments: { title: "Buy groceries" } });
    const data = parsedContent(result) as { success: boolean; todo: TodoItem };
    expect(data.success).toBe(true);
    expect(data.todo.title).toBe("Buy groceries");
    expect(data.todo.priority).toBe("medium");
    expect(data.todo.completed).toBe(false);
    expect(data.todo.tags).toEqual([]);
    expect(typeof data.todo.id).toBe("string");
  });

  it("adds a todo with explicit priority and tags", async () => {
    const result = await client.callTool({
      name: "add_todo",
      arguments: { title: "Deploy service", priority: "high", tags: ["devops", "urgent"] },
    });
    const data = parsedContent(result) as { success: boolean; todo: TodoItem };
    expect(data.success).toBe(true);
    expect(data.todo.priority).toBe("high");
    expect(data.todo.tags).toEqual(["devops", "urgent"]);
  });

  it("adds a todo with low priority", async () => {
    const result = await client.callTool({
      name: "add_todo",
      arguments: { title: "Read a book", priority: "low" },
    });
    const data = parsedContent(result) as { success: boolean; todo: TodoItem };
    expect(data.todo.priority).toBe("low");
  });

  it("stores the todo in the in-memory map", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Check email" } });
    expect(todos.size).toBe(1);
  });

  it("returns isError for an empty title", async () => {
    const result = await client.callTool({ name: "add_todo", arguments: { title: "   " } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("empty");
  });

  it("returns isError when title exceeds max length", async () => {
    const longTitle = "a".repeat(MAX_TITLE_LENGTH + 1);
    const result = await client.callTool({ name: "add_todo", arguments: { title: longTitle } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("maximum length");
  });
});

// ── list_todos ────────────────────────────────────────────────────────────────

describe("list_todos", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("returns an empty list when no todos exist", async () => {
    const result = await client.callTool({ name: "list_todos", arguments: {} });
    const data = parsedContent(result) as { success: boolean; count: number; todos: TodoItem[] };
    expect(data.success).toBe(true);
    expect(data.count).toBe(0);
    expect(data.todos).toEqual([]);
  });

  it("returns all todos when no filter is applied", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Task A" } });
    await client.callTool({ name: "add_todo", arguments: { title: "Task B" } });
    const result = await client.callTool({ name: "list_todos", arguments: {} });
    const data = parsedContent(result) as { count: number; todos: TodoItem[] };
    expect(data.count).toBe(2);
  });

  it("filters by completed=false", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Pending task" } });
    const result = await client.callTool({ name: "list_todos", arguments: { completed: false } });
    const data = parsedContent(result) as { count: number; todos: TodoItem[] };
    expect(data.count).toBe(1);
    expect(data.todos[0].completed).toBe(false);
  });

  it("filters by completed=true after completing a todo", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Finish report" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    await client.callTool({ name: "complete_todo", arguments: { todo_id: addData.todo.id } });

    const result = await client.callTool({ name: "list_todos", arguments: { completed: true } });
    const data = parsedContent(result) as { count: number; todos: TodoItem[] };
    expect(data.count).toBe(1);
    expect(data.todos[0].completed).toBe(true);
  });

  it("filters by priority", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "High task", priority: "high" } });
    await client.callTool({ name: "add_todo", arguments: { title: "Low task", priority: "low" } });
    const result = await client.callTool({ name: "list_todos", arguments: { priority: "high" } });
    const data = parsedContent(result) as { count: number; todos: TodoItem[] };
    expect(data.count).toBe(1);
    expect(data.todos[0].priority).toBe("high");
  });

  it("filters by tag (case-insensitive)", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Tagged task", tags: ["Work"] } });
    await client.callTool({ name: "add_todo", arguments: { title: "Untagged task" } });
    const result = await client.callTool({ name: "list_todos", arguments: { tag: "work" } });
    const data = parsedContent(result) as { count: number; todos: TodoItem[] };
    expect(data.count).toBe(1);
    expect(data.todos[0].title).toBe("Tagged task");
  });

  it("returns empty list when tag filter matches nothing", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Some task", tags: ["alpha"] } });
    const result = await client.callTool({ name: "list_todos", arguments: { tag: "beta" } });
    const data = parsedContent(result) as { count: number };
    expect(data.count).toBe(0);
  });
});

// ── get_todo ──────────────────────────────────────────────────────────────────

describe("get_todo", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("retrieves an existing todo by ID", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Find me" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    const result = await client.callTool({ name: "get_todo", arguments: { todo_id: id } });
    const data = parsedContent(result) as { success: boolean; todo: TodoItem };
    expect(data.success).toBe(true);
    expect(data.todo.id).toBe(id);
    expect(data.todo.title).toBe("Find me");
  });

  it("returns isError for a non-existent UUID", async () => {
    const fakeId = randomUUID();
    const result = await client.callTool({ name: "get_todo", arguments: { todo_id: fakeId } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("not found");
  });

  it("returns isError for an invalid ID format", async () => {
    const result = await client.callTool({ name: "get_todo", arguments: { todo_id: "not-a-uuid" } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("Invalid ID format");
  });
});

// ── complete_todo ─────────────────────────────────────────────────────────────

describe("complete_todo", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("marks a todo as completed", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Finish tests" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    const result = await client.callTool({ name: "complete_todo", arguments: { todo_id: id } });
    const data = parsedContent(result) as { success: boolean; todo: TodoItem };
    expect(data.success).toBe(true);
    expect(data.todo.completed).toBe(true);
    expect(data.todo.completedAt).not.toBeNull();
  });

  it("persists the completed state in the store", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Persist me" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    await client.callTool({ name: "complete_todo", arguments: { todo_id: id } });
    expect(todos.get(id)?.completed).toBe(true);
  });

  it("returns isError for a non-existent UUID", async () => {
    const fakeId = randomUUID();
    const result = await client.callTool({ name: "complete_todo", arguments: { todo_id: fakeId } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("not found");
  });

  it("returns isError when todo is already completed", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Already done" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    await client.callTool({ name: "complete_todo", arguments: { todo_id: id } });
    const result = await client.callTool({ name: "complete_todo", arguments: { todo_id: id } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("already completed");
  });

  it("returns isError for an invalid ID format", async () => {
    const result = await client.callTool({ name: "complete_todo", arguments: { todo_id: "bad-id" } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("Invalid ID format");
  });
});

// ── delete_todo ───────────────────────────────────────────────────────────────

describe("delete_todo", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("deletes an existing todo", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Delete me" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    const result = await client.callTool({ name: "delete_todo", arguments: { todo_id: id } });
    const data = parsedContent(result) as { success: boolean; deleted: TodoItem; message: string };
    expect(data.success).toBe(true);
    expect(data.deleted.id).toBe(id);
    expect(data.message).toContain("deleted successfully");
  });

  it("removes the todo from the in-memory store", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Gone soon" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    await client.callTool({ name: "delete_todo", arguments: { todo_id: id } });
    expect(todos.has(id)).toBe(false);
  });

  it("returns isError for a non-existent UUID", async () => {
    const fakeId = randomUUID();
    const result = await client.callTool({ name: "delete_todo", arguments: { todo_id: fakeId } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("not found");
  });

  it("returns isError for an invalid ID format", async () => {
    const result = await client.callTool({ name: "delete_todo", arguments: { todo_id: "not-valid" } });
    expect(result.isError).toBe(true);
    expect(textContent(result).text).toContain("Invalid ID format");
  });

  it("cannot get a deleted todo", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Ephemeral" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    const id = addData.todo.id;

    await client.callTool({ name: "delete_todo", arguments: { todo_id: id } });
    const getResult = await client.callTool({ name: "get_todo", arguments: { todo_id: id } });
    expect(getResult.isError).toBe(true);
  });
});

// ── summarize_workload ────────────────────────────────────────────────────────

describe("summarize_workload", () => {
  let todos: Map<string, TodoItem>;
  let client: Client;

  beforeEach(async () => {
    todos = new Map();
    client = await makeClient(todos);
  });

  it("returns zero counts when no todos exist", async () => {
    const result = await client.callTool({ name: "summarize_workload", arguments: {} });
    const data = parsedContent(result) as {
      success: boolean;
      summary: { total: number; completed: number; pending: number };
    };
    expect(data.success).toBe(true);
    expect(data.summary.total).toBe(0);
    expect(data.summary.completed).toBe(0);
    expect(data.summary.pending).toBe(0);
  });

  it("reflects correct counts after adding todos", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "Task 1", priority: "high" } });
    await client.callTool({ name: "add_todo", arguments: { title: "Task 2", priority: "low" } });
    await client.callTool({ name: "add_todo", arguments: { title: "Task 3", priority: "medium" } });

    const result = await client.callTool({ name: "summarize_workload", arguments: {} });
    const data = parsedContent(result) as {
      summary: { total: number; pending: number; completed: number };
    };
    expect(data.summary.total).toBe(3);
    expect(data.summary.pending).toBe(3);
    expect(data.summary.completed).toBe(0);
  });

  it("updates counts after completing a todo", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "Complete me" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    await client.callTool({ name: "complete_todo", arguments: { todo_id: addData.todo.id } });

    const result = await client.callTool({ name: "summarize_workload", arguments: {} });
    const data = parsedContent(result) as {
      summary: { total: number; pending: number; completed: number };
    };
    expect(data.summary.total).toBe(1);
    expect(data.summary.completed).toBe(1);
    expect(data.summary.pending).toBe(0);
  });

  it("includes byPriority breakdown", async () => {
    await client.callTool({ name: "add_todo", arguments: { title: "H1", priority: "high" } });
    await client.callTool({ name: "add_todo", arguments: { title: "H2", priority: "high" } });
    await client.callTool({ name: "add_todo", arguments: { title: "L1", priority: "low" } });

    const result = await client.callTool({ name: "summarize_workload", arguments: {} });
    const data = parsedContent(result) as {
      summary: { byPriority: { all: { high: number; low: number; medium: number } } };
    };
    expect(data.summary.byPriority.all.high).toBe(2);
    expect(data.summary.byPriority.all.low).toBe(1);
    expect(data.summary.byPriority.all.medium).toBe(0);
  });

  it("updates counts after deleting a todo", async () => {
    const addResult = await client.callTool({ name: "add_todo", arguments: { title: "To be deleted" } });
    const addData = parsedContent(addResult) as { todo: TodoItem };
    await client.callTool({ name: "delete_todo", arguments: { todo_id: addData.todo.id } });

    const result = await client.callTool({ name: "summarize_workload", arguments: {} });
    const data = parsedContent(result) as { summary: { total: number } };
    expect(data.summary.total).toBe(0);
  });
});