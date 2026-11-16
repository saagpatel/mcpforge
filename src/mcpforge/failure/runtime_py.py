"""Vendable stdlib runtime: type, required, properties, items, enum schema keywords.

A cancellation directive precedes the steps it counts; a hang counts as a step.
The descriptor receives ``_released`` and, on cancellation, ``_cancelled_outcome``.
Cancellation is always re-raised.
"""

import asyncio
import inspect
import json
import math

_TRANSIENT = {"timeout", "upstream_error", "cursor_expired", "page_shifted"}
# How long a stopped stream's in-flight step may settle before it is cancelled, so a
# generator already running its own finalizer is not interrupted (TypeScript's
# cleanupTimeoutMs default).
CLEANUP_GRACE_S = 1.0


def resolve_failure(contract, kind, have_partial, detail):
    """Mirror the shared resolver; pagination cursors are outside this runtime."""
    partial = bool(contract["partial_result_allowed"] and have_partial and kind != "cancelled")
    return {
        "status": "incomplete" if partial else "failed",
        "failure": {
            "kind": kind,
            "retryable": bool(contract["retryable"] and kind in _TRANSIENT),
            "partial_result": partial,
            "detail": detail,
        },
    }


def _valid(value, schema):
    def json_equal(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return type(left) is type(right) and left == right
        if isinstance(left, dict) and isinstance(right, dict):
            return left.keys() == right.keys() and all(
                json_equal(left[key], right[key]) for key in left
            )
        if isinstance(left, list) and isinstance(right, list):
            return len(left) == len(right) and all(
                map(lambda pair: json_equal(*pair), zip(left, right))
            )
        return left == right

    if "enum" in schema and not any(json_equal(value, option) for option in schema["enum"]):
        return False
    types = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "number": lambda v: (
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        ),
        "integer": lambda v: (
            isinstance(v, (int, float))
            and not isinstance(v, bool)
            and math.isfinite(v)
            and v == int(v)
        ),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if "type" in schema and (schema["type"] not in types or not types[schema["type"]](value)):
        return False
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            return False
        if any(
            key in value and not _valid(value[key], child)
            for key, child in schema.get("properties", {}).items()
        ):
            return False
    if isinstance(value, list) and "items" in schema:
        if any(not _valid(item, schema["items"]) for item in value):
            return False
    return True


async def call_operation(operation, contract, timeout_s, response_schema=None):
    """Run an async callable or iterator; cancellation propagates after cleanup."""
    items = []
    stopped = False
    finalizing = False
    stepping = False

    def outcome(kind, detail):
        result = resolve_failure(contract, kind, bool(items), detail)
        result["items"] = list(items) if result["failure"]["partial_result"] else []
        return result

    async def run():
        nonlocal finalizing, stepping
        value = operation() if callable(operation) else operation
        if inspect.isawaitable(value):
            value = await value
        if hasattr(value, "__aiter__"):
            iterator = value.__aiter__()
            try:
                while not stopped:
                    stepping = True
                    try:
                        item = await anext(iterator)
                    except StopAsyncIteration:
                        break
                    finally:
                        stepping = False
                    if stopped:
                        break
                    if response_schema is not None and not _valid(item, response_schema):
                        return outcome("malformed", "upstream returned malformed data")
                    items.append(item)
            finally:
                finalizing = True
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    # Consume and close in the same task/Context so generator
                    # finalizers can reset ContextVar tokens created on entry.
                    await close()
        elif not stopped:
            if response_schema is not None and not _valid(value, response_schema):
                return outcome("malformed", "upstream returned malformed data")
            items.append(value)
        return {"status": "complete", "failure": None, "items": items}

    # Own the task separately: wait_for can replace caller cancellation with an
    # exception raised by the operation's finalizer, or accept a late result if
    # the operation suppresses cancellation.
    timeout = None if timeout_s is None else max(0, timeout_s)
    task = asyncio.create_task(run())
    caller = asyncio.current_task()
    cancellation_requests = caller.cancelling()
    caller_cancelled = False
    timed_out = False
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        timed_out = not done
    except asyncio.CancelledError:
        caller_cancelled = True
    if timed_out or caller_cancelled:
        stopped = True
        if stepping and not finalizing:
            # A generator step may already be running its own finalizer (natural
            # exhaustion or an error inside anext); cancelling now would interrupt
            # that cleanup. Give the step a bounded grace to settle first.
            grace = asyncio.ensure_future(asyncio.wait({task}, timeout=CLEANUP_GRACE_S))
            while not grace.done():
                try:
                    await asyncio.shield(grace)
                except asyncio.CancelledError:
                    caller_cancelled = True
        # Let an active finalizer finish in its owning task. The shield below
        # protects that task from repeated caller cancellation as well.
        if not finalizing and not task.done():
            task.cancel()

    # Shield cleanup from repeated caller cancellation, but remember every
    # cancellation independently of how the operation eventually terminates.
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            caller_cancelled = caller_cancelled or caller.cancelling() > cancellation_requests
        except Exception:
            break
    try:
        result = task.result()
    except asyncio.CancelledError:
        if not timed_out:
            raise
    except Exception:
        result = outcome("upstream_error", "upstream failed")
    if caller_cancelled:
        raise asyncio.CancelledError
    if timed_out:
        return outcome("timeout", "upstream timed out")
    return result


async def call_upstream(upstream, contract, timeout_s, response_schema=None):
    """Run a descriptor or real operation and return a normalized outcome."""
    if callable(upstream) or hasattr(upstream, "__aiter__"):
        return await call_operation(upstream, contract, timeout_s, response_schema)
    items = []

    def outcome(kind, detail):
        result = resolve_failure(contract, kind, bool(items), detail)
        result["items"] = list(items) if result["failure"]["partial_result"] else []
        return result

    async def run():
        remaining = None
        for step in upstream["script"]:
            if "cancel_after_steps" in step:
                remaining = step["cancel_after_steps"]
                if remaining == 0:
                    raise asyncio.CancelledError
                continue
            if "hang" in step and step["hang"]:
                if remaining == 1:
                    asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)
                await asyncio.Event().wait()
            elif "emit" in step or "emit_raw" in step:
                try:

                    def reject_constant(value):
                        raise ValueError(f"invalid JSON constant: {value}")

                    value = (
                        step["emit"]
                        if "emit" in step
                        else json.loads(step["emit_raw"], parse_constant=reject_constant)
                    )
                except (ValueError, TypeError):
                    return outcome("malformed", "upstream returned malformed data")
                if not _valid(value, upstream["response_schema"]):
                    return outcome("malformed", "upstream returned malformed data")
                items.append(value)
            if remaining is not None:
                remaining -= 1
                if remaining == 0:
                    raise asyncio.CancelledError
        return {"status": "complete", "failure": None, "items": items}

    try:
        try:
            return await asyncio.wait_for(run(), timeout=timeout_s)
        except TimeoutError:
            return outcome("timeout", "upstream timed out")
        except asyncio.CancelledError:
            upstream["_cancelled_outcome"] = outcome("cancelled", "upstream cancelled")
            raise
    finally:
        upstream["_released"] = True
