/** Deterministic resource probes for the canonical and generated runtimes. */
import type { callOperation as runtimeCallOperation, Outcome } from "../../src/mcpforge/failure/runtime_ts.ts";

export async function lifecycleCase(callOperation: typeof runtimeCallOperation, mode: string) {
  const controller = new AbortController();
  let acquired = 0;
  let closed = 0;
  let cleaned = false;
  let settled = false;
  let reads = 0;
  let releaseFactory!: () => void;
  let releaseNext!: () => void;
  let releaseCleanup!: () => void;
  let started!: () => void;
  let cleanupDone!: () => void;
  const ready = new Promise<void>((resolve) => { started = resolve; });
  const cleanup = new Promise<void>((resolve) => { cleanupDone = resolve; });
  const factoryGate = new Promise<void>((resolve) => { releaseFactory = resolve; });
  const nextGate = new Promise<void>((resolve) => { releaseNext = resolve; });
  const cleanupGate = new Promise<void>((resolve) => { releaseCleanup = resolve; });
  const isLate = mode.startsWith("late_");
  const cancels = mode.includes("cancel");
  const failsCleanup = mode.includes("cleanup_error");
  const stream = {
    [Symbol.asyncIterator]() {
      acquired += 1;
      return {
        async next() {
          reads += 1;
          if (reads === 1) return { done: false, value: { value: 1 } };
          if (mode.startsWith("malformed")) return { done: false, value: "invalid" };
          if (mode === "next_error") throw new Error("private upstream detail");
          if (mode.includes("timeout") || (cancels && !mode.startsWith("cleanup_"))) {
            started();
            if (!mode.startsWith("late_next")) {
              controllerForOperation!.addEventListener("abort", releaseNext, { once: true });
            }
            await nextGate;
            if (mode.startsWith("late_next_error")) throw new Error("late next failure");
          }
          return { done: true, value: undefined };
        },
        async return() {
          closed += 1;
          try {
            if (mode.startsWith("cleanup_cancel")) {
              started();
              await cleanupGate;
            }
            // Make callers prove they await asynchronous cleanup on normal exits.
            await new Promise<void>((resolve) => setTimeout(resolve, 1));
            if (failsCleanup) throw new Error("private cleanup detail");
            return { done: true, value: undefined };
          } finally {
            cleaned = true;
            cleanupDone();
          }
        },
      };
    },
  };
  let controllerForOperation: AbortSignal | undefined;
  const operation = async (signal: AbortSignal) => {
    controllerForOperation = signal;
    try {
      if (isLate && !mode.startsWith("late_next")) {
        started();
        await factoryGate;
        if (mode.startsWith("late_reject")) throw new Error("late factory failure");
        if (mode.startsWith("late_value")) return { value: 9 };
      }
      return stream;
    } finally {
      settled = true;
    }
  };
  const contract = { retryable: true, partial_result_allowed: true };
  const schema = { type: "object", required: ["value"] };
  let cancellationOutcome: Outcome | undefined;
  let escaped = false;
  // Observe rejection immediately so tests cannot accidentally hide an orphan.
  const pending = callOperation(operation, contract, mode.includes("timeout") ? 20 : 1000,
    schema, {
      signal: controller.signal,
      onCancelled: (value) => { cancellationOutcome = value; },
    }).then((outcome) => outcome, (error: Error) => {
      if (error.message !== "cancelled") throw error;
      escaped = true;
      return undefined;
    });
  if (cancels) {
    await ready;
    controller.abort();
    if (mode.startsWith("cleanup_")) releaseCleanup();
  }
  const outcome = await pending;
  if (!mode.includes("timeout") && !cancels && !cleaned) {
    throw new Error("normal response preceded cleanup");
  }
  if (isLate) {
    releaseFactory();
    releaseNext();
  }
  if (mode.startsWith("late_value") || mode.startsWith("late_reject")) {
    // Drain the late factory rejection through the run promise's race handler.
    await new Promise<void>((resolve) => setTimeout(resolve, 1));
  } else {
    await cleanup;
  }
  return { outcome: escaped ? cancellationOutcome : outcome, escaped,
    acquired, closed, cleaned, settled, reads };
}
