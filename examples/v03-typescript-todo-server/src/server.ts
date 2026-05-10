import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { randomUUID } from "crypto";

// ── In-memory store ──────────────────────────────────────────────────────────

interface TodoItem {
  id: string;
  title: string;
  priority: "low" | "medium" | "high";
  tags: string[];
  completed: boolean;
  createdAt: string;
  completedAt: string | null;
}

const todos = new Map<string, TodoItem>();

const VALID_PRIORITIES = ["low", "medium", "high"] as const;
type Priority = (typeof VALID_PRIORITIES)[number];
const MAX_TITLE_LENGTH = 500;

function isValidPriority(p: string): p is Priority {
  return (VALID_PRIORITIES as readonly string[]).includes(p);
}

function isValidUUID(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}

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

// ── Server ───────────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "TypeScript Todo Workflow",
  version: "0.1.0",
});

// ── Tools ────────────────────────────────────────────────────────────────────

server.tool(
  "add_todo",
  "Add a new todo item with a title and optional priority and tags.",
  {
    title: z.string().describe("The title or description of the todo item"),
    priority: z
      .enum(["low", "medium", "high"])
      .optional()
      .default("medium")
      .describe("Priority level: 'low', 'medium', or 'high'"),
    tags: z
      .array(z.string())
      .optional()
      .describe("Optional list of tags to categorize the todo"),
  },
  async ({ title, priority, tags }) => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      throw new Error("Title must not be empty.");
    }
    if (trimmedTitle.length > MAX_TITLE_LENGTH) {
      throw new Error(
        `Title exceeds maximum length of ${MAX_TITLE_LENGTH} characters.`
      );
    }

    const resolvedPriority: Priority = priority ?? "medium";
    if (!isValidPriority(resolvedPriority)) {
      throw new Error(
        `Invalid priority value "${resolvedPriority}". Must be one of: low, medium, high.`
      );
    }

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

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ success: true, todo }),
        },
      ],
    };
  }
);

server.tool(
  "list_todos",
  "List all todo items, optionally filtered by completion status, priority, or tag.",
  {
    completed: z
      .boolean()
      .optional()
      .describe("Filter by completion status; omit to return all todos"),
    priority: z
      .enum(["low", "medium", "high"])
      .optional()
      .describe("Filter by priority level: 'low', 'medium', or 'high'"),
    tag: z.string().optional().describe("Filter by a specific tag"),
  },
  async ({ completed, priority, tag }) => {
    if (priority !== undefined && !isValidPriority(priority)) {
      throw new Error(
        `Invalid priority value "${priority}". Must be one of: low, medium, high.`
      );
    }

    let results = Array.from(todos.values());

    if (completed !== undefined) {
      results = results.filter((t) => t.completed === completed);
    }
    if (priority !== undefined) {
      results = results.filter((t) => t.priority === priority);
    }
    if (tag !== undefined) {
      const normalizedTag = tag.trim().toLowerCase();
      results = results.filter((t) =>
        t.tags.some((tg) => tg.toLowerCase() === normalizedTag)
      );
    }

    results.sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ success: true, count: results.length, todos: results }),
        },
      ],
    };
  }
);

server.tool(
  "get_todo",
  "Retrieve a single todo item by its unique ID.",
  {
    todo_id: z.string().describe("The unique ID of the todo item"),
  },
  async ({ todo_id }) => {
    if (!isValidUUID(todo_id)) {
      throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
    }

    const todo = todos.get(todo_id);
    if (!todo) {
      throw new Error(`Todo with ID "${todo_id}" not found.`);
    }

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ success: true, todo }),
        },
      ],
    };
  }
);

server.tool(
  "complete_todo",
  "Mark a todo item as completed by its unique ID.",
  {
    todo_id: z
      .string()
      .describe("The unique ID of the todo item to mark as complete"),
  },
  async ({ todo_id }) => {
    if (!isValidUUID(todo_id)) {
      throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
    }

    const todo = todos.get(todo_id);
    if (!todo) {
      throw new Error(`Todo with ID "${todo_id}" not found.`);
    }
    if (todo.completed) {
      throw new Error(`Todo with ID "${todo_id}" is already completed.`);
    }

    todo.completed = true;
    todo.completedAt = new Date().toISOString();
    todos.set(todo_id, todo);

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ success: true, todo }),
        },
      ],
    };
  }
);

server.tool(
  "delete_todo",
  "Delete a todo item by its unique ID.",
  {
    todo_id: z
      .string()
      .describe("The unique ID of the todo item to delete"),
  },
  async ({ todo_id }) => {
    if (!isValidUUID(todo_id)) {
      throw new Error(`Invalid ID format: "${todo_id}". Expected a UUID.`);
    }

    const todo = todos.get(todo_id);
    if (!todo) {
      throw new Error(`Todo with ID "${todo_id}" not found.`);
    }

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

server.tool(
  "summarize_workload",
  "Return a structured summary of the current todo workload, including counts by status and priority.",
  {},
  async () => {
    const summary = buildSummary();

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({ success: true, summary }),
        },
      ],
    };
  }
);

// ── Resources ────────────────────────────────────────────────────────────────

server.resource(
  "all_todos_resource",
  "todos://all",
  {
    description: "Read-only view of all in-memory todo items for contextual reference.",
    mimeType: "application/json",
  },
  async () => {
    const allTodos = Array.from(todos.values()).sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );

    return {
      contents: [
        {
          uri: "todos://all",
          mimeType: "application/json",
          text: JSON.stringify({ count: allTodos.length, todos: allTodos }),
        },
      ],
    };
  }
);

server.resource(
  "workload_summary_resource",
  "todos://summary",
  {
    description:
      "Read-only workload summary showing counts by status and priority.",
    mimeType: "application/json",
  },
  async () => {
    const summary = buildSummary();

    return {
      contents: [
        {
          uri: "todos://summary",
          mimeType: "application/json",
          text: JSON.stringify(summary),
        },
      ],
    };
  }
);

// ── Prompts ──────────────────────────────────────────────────────────────────

server.prompt(
  "workload_review",
  "Generate a concise review of the current todo workload, highlighting high-priority and incomplete items.",
  {},
  async () => {
    const summary = buildSummary();
    const pendingHigh = Array.from(todos.values()).filter(
      (t) => !t.completed && t.priority === "high"
    );

    const context = JSON.stringify({ summary, highPriorityPending: pendingHigh }, null, 2);

    return {
      messages: [
        {
          role: "user" as const,
          content: {
            type: "text" as const,
            text: `Here is the current todo workload data:\n\n${context}\n\nReview the current todo list. Identify all incomplete items, call out any high-priority tasks that need immediate attention, and suggest a recommended order of completion based on priority and workload balance.`,
          },
        },
      ],
    };
  }
);

server.prompt(
  "daily_standup",
  "Produce a daily standup-style summary of completed and pending todos.",
  {},
  async () => {
    const allTodos = Array.from(todos.values());
    const completed = allTodos.filter((t) => t.completed);
    const pending = allTodos.filter((t) => !t.completed);
    const highPriorityPending = pending.filter((t) => t.priority === "high");

    const context = JSON.stringify(
      { completed, pending, highPriorityPending },
      null,
      2
    );

    return {
      messages: [
        {
          role: "user" as const,
          content: {
            type: "text" as const,
            text: `Here is the current todo data:\n\n${context}\n\nProduce a daily standup summary. List what has been completed, what is still pending, and flag any blockers or high-priority items that remain unfinished.`,
          },
        },
      ],
    };
  }
);

// ── Transport ────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
