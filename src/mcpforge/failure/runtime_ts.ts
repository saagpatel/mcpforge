/** Dependency-free failure runtime suitable for copying into generated servers.
 *
 * The validator deliberately supports only the JSON Schema subset used by the
 * synthetic fixtures: type, required, properties, items, and enum.
 */
export type FailureKind =
  | "timeout"
  | "malformed"
  | "cancelled"
  | "upstream_error"
  | "cursor_expired"
  | "page_shifted";

export type FailureContract = {
  retryable: boolean;
  partial_result_allowed: boolean;
};

export type Outcome = {
  status: "complete" | "incomplete" | "failed";
  failure: null | {
    kind: FailureKind;
    retryable: boolean;
    partial_result: boolean;
    detail: string;
  };
  items: unknown[];
};

type Schema = {
  type?: string;
  required?: string[];
  properties?: Record<string, Schema>;
  items?: Schema;
  enum?: unknown[];
};

type Step =
  | { emit: unknown }
  | { emit_raw: string }
  | { hang: true }
  | { cancel_after_steps: number };

export type Upstream = {
  name?: string;
  response_schema: Schema;
  script: Step[];
};

export type RuntimeOptions = {
  /** External caller cancellation. */
  signal?: AbortSignal;
  /** Observe the normalized cancellation outcome before cancellation escapes. */
  onCancelled?: (outcome: Outcome) => void;
};

/** An operation receives the runtime's cancellation signal and returns one
 * value or an async iterable of partial values. */
export type Operation =
  | ((signal: AbortSignal) => Promise<unknown> | AsyncIterable<unknown>)
  | AsyncIterable<unknown>;

const transientKinds = new Set<FailureKind>([
  "timeout", "upstream_error", "cursor_expired", "page_shifted",
]);

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
    return `{${entries.map(([key, child]) => `${JSON.stringify(key)}:${stableJson(child)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

/** The TypeScript equivalent of mcpforge.contracts.resolve_outcome. */
export function resolveOutcome(
  contract: FailureContract,
  kind: FailureKind,
  havePartial: boolean,
  detail: string,
): Outcome {
  const partial = contract.partial_result_allowed && havePartial && kind !== "cancelled";
  return {
    status: partial ? "incomplete" : "failed",
    failure: {
      kind,
      retryable: contract.retryable && transientKinds.has(kind),
      partial_result: partial,
      detail,
    },
    items: [],
  };
}

function schemaError(value: unknown, schema: Schema, path = "$" ): string | undefined {
  if (schema.enum && !schema.enum.some((candidate) => stableJson(candidate) === stableJson(value))) {
    return `${path} is not an allowed enum value`;
  }
  if (schema.type) {
    const valid = schema.type === "object"
      ? value !== null && typeof value === "object" && !Array.isArray(value)
      : schema.type === "array"
        ? Array.isArray(value)
        : schema.type === "integer"
          ? typeof value === "number" && Number.isInteger(value)
          : schema.type === "number"
            ? typeof value === "number" && Number.isFinite(value)
            : schema.type === "null"
              ? value === null
              : typeof value === schema.type;
    if (!valid) return `${path} must be ${schema.type}`;
  }
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const objectValue = value as Record<string, unknown>;
    for (const key of schema.required ?? []) {
      if (!Object.hasOwn(objectValue, key)) return `${path}.${key} is required`;
    }
    for (const [key, childSchema] of Object.entries(schema.properties ?? {})) {
      if (Object.hasOwn(objectValue, key)) {
        const error = schemaError(objectValue[key], childSchema, `${path}.${key}`);
        if (error) return error;
      }
    }
  }
  if (Array.isArray(value) && schema.items) {
    for (let index = 0; index < value.length; index += 1) {
      const error = schemaError(value[index], schema.items, `${path}[${index}]`);
      if (error) return error;
    }
  }
  return undefined;
}

function errorOutcome(contract: FailureContract, kind: FailureKind, partial: unknown[], detail: string): Outcome {
  const resolved = resolveOutcome(contract, kind, partial.length > 0, detail);
  return { ...resolved, items: resolved.status === "incomplete" ? [...partial] : [] };
}

/** Execute an upstream operation inside the failure contract.
 *
 * `operation` receives an AbortSignal and may return a single value or an
 * async iterable. Streamed values are validated as they arrive, so allowed
 * partial results survive timeout and malformed-data outcomes.
 */
export async function callOperation(
  operation: Operation,
  contract: FailureContract,
  timeoutMs: number,
  responseSchema: Schema = {},
  options: RuntimeOptions = {},
): Promise<Outcome> {
  const controller = new AbortController();
  const items: unknown[] = [];
  let activeIterator: AsyncIterator<unknown> | undefined;
  const timeoutReason = Symbol("timeout");
  const cancelledReason = Symbol("cancelled");
  let cancel: (() => void) | undefined;
  const cancelled = new Promise<never>((_resolve, reject) => {
    cancel = () => reject(cancelledReason);
  });
  const onAbort = () => {
    cancel?.();
    controller.abort("cancelled");
  };
  if (options.signal?.aborted) onAbort();
  options.signal?.addEventListener("abort", onAbort, { once: true });

  const run = async (): Promise<Outcome> => {
    if (controller.signal.aborted) throw cancelledReason;
    const result = typeof operation === "function"
      ? await operation(controller.signal)
      : operation;
    if (controller.signal.aborted) {
      throw controller.signal.reason === "timeout" ? timeoutReason : cancelledReason;
    }
    if (result !== null && typeof result === "object" && Symbol.asyncIterator in result) {
      const iterator = (result as AsyncIterable<unknown>)[Symbol.asyncIterator]();
      activeIterator = iterator;
      while (true) {
        const next = await iterator.next();
        if (controller.signal.aborted) {
          throw controller.signal.reason === "timeout" ? timeoutReason : cancelledReason;
        }
        if (next.done) break;
        if (schemaError(next.value, responseSchema)) {
          return errorOutcome(contract, "malformed", items, "upstream returned malformed data");
        }
        items.push(next.value);
      }
    } else {
      if (schemaError(result, responseSchema)) {
        return errorOutcome(contract, "malformed", items, "upstream returned malformed data");
      }
      items.push(result);
    }
    return { status: "complete", failure: null, items };
  };

  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_resolve, reject) => {
    timeoutId = setTimeout(() => {
      reject(timeoutReason);
      controller.abort("timeout");
    }, Math.max(0, timeoutMs));
  });
  try {
    return await Promise.race([run(), timeout, cancelled]);
  } catch (error) {
    if (error === cancelledReason) {
      const outcome = errorOutcome(contract, "cancelled", items, "upstream cancelled");
      options.onCancelled?.(outcome);
      throw new Error("cancelled");
    }
    if (error === timeoutReason) return errorOutcome(contract, "timeout", items, "upstream timed out");
    return errorOutcome(contract, "upstream_error", items, "upstream failed");
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", onAbort);
    controller.abort("released");
    if (activeIterator?.return) void activeIterator.return().catch(() => undefined);
  }
}

/** Run a descriptor's deterministic script and normalize its outcome.
 *
 * A hang is an unresolved promise, so timeout behavior is event-driven rather
 * than dependent on a racing sleep. Script cancellation is useful to exercise
 * the same caller-cancellation path as an AbortSignal.
 */
export async function callUpstream(
  upstream: Upstream,
  contract: FailureContract,
  timeoutMs: number,
  options: RuntimeOptions = {},
): Promise<Outcome> {
  const controller = new AbortController();
  const items: unknown[] = [];
  let cancellation: (() => void) | undefined;
  const cancelled = new Promise<never>((_resolve, reject) => {
    cancellation = () => reject(new Error("cancelled"));
  });
  controller.signal.addEventListener("abort", () => {
    if (controller.signal.reason === "cancelled") cancellation?.();
  });
  const onAbort = () => controller.abort("cancelled");
  if (options.signal?.aborted) onAbort();
  options.signal?.addEventListener("abort", onAbort, { once: true });

  const run = async (): Promise<Outcome> => {
    let cancelAfter: number | undefined;
    if (controller.signal.aborted) throw new Error("cancelled");
    for (const step of upstream.script) {
      if ("cancel_after_steps" in step) {
        cancelAfter = step.cancel_after_steps;
        if (cancelAfter === 0) {
          controller.abort("cancelled");
          throw new Error("cancelled");
        }
        continue;
      }
      if ("hang" in step) {
        if (cancelAfter !== undefined && cancelAfter > 0) cancelAfter -= 1;
        if (cancelAfter === 0) controller.abort("cancelled");
        await new Promise<never>((_resolve, reject) => {
          const stop = () => reject(new Error(String(controller.signal.reason ?? "cancelled")));
          if (controller.signal.aborted) stop();
          else controller.signal.addEventListener("abort", stop, { once: true });
        });
      }
      let value: unknown;
      if ("emit_raw" in step) {
        try {
          value = JSON.parse(step.emit_raw);
        } catch {
          return errorOutcome(contract, "malformed", items, "upstream returned malformed data");
        }
      } else if ("emit" in step) {
        value = step.emit;
      } else {
        throw new Error("invalid upstream step");
      }
      const validationError = schemaError(value, upstream.response_schema);
      if (validationError) return errorOutcome(contract, "malformed", items, "upstream returned malformed data");
      items.push(value);
      if (cancelAfter !== undefined && cancelAfter > 0) {
        cancelAfter -= 1;
        if (cancelAfter === 0) {
          controller.abort("cancelled");
          throw new Error("cancelled");
        }
      }
    }
    return { status: "complete", failure: null, items };
  };

  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_resolve, reject) => {
    timeoutId = setTimeout(() => {
      controller.abort("timeout");
      reject(new Error("timeout"));
    }, Math.max(0, timeoutMs));
  });
  try {
    return await Promise.race([run(), timeout, cancelled]);
  } catch (error) {
    const reason = error instanceof Error ? error.message : "upstream error";
    if (reason === "cancelled") {
      const outcome = errorOutcome(contract, "cancelled", items, "upstream cancelled");
      options.onCancelled?.(outcome);
      throw error;
    }
    if (reason === "timeout") return errorOutcome(contract, "timeout", items, "upstream timed out");
    return errorOutcome(contract, "upstream_error", items, reason);
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", onAbort);
    controller.abort("released");
  }
}
