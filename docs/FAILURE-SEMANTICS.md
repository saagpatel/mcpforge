# Failure semantics

Python generation opts into these semantics when at least one tool declares a
non-null `failure_contract` or `pagination`. The writer then includes
`failure_runtime.py` and `failure_contracts.json`, with an explicit or derived
default contract for every tool. Plans without either field retain the legacy
artifact set. OpenAPI-derived pagination opts in automatically.

mcpforge uses the vocabulary in `mcpforge.contracts`: `timeout`, `malformed`,
`cancelled`, `upstream_error`, `cursor_expired`, and `page_shifted`. A
`FailureContract` records whether the tool may be retried and whether partial
results may be returned. Every failure is resolved by the same outcome rules.

| Condition | `retryable` | `partial_result` | `status` |
|---|---|---|---|
| Failure kind is transient and contract allows retry | true | determined below | determined below |
| `have_partial` and contract allows partial results, except cancellation | contract and kind | true | `incomplete` |
| All other failures | contract and kind | false | `failed` |
| No failure occurred | — | — | `complete` |

Only `timeout`, `upstream_error`, `cursor_expired`, and `page_shifted` are
transient. `malformed` and `cancelled` are never retryable. Cancellation never
returns partial data: the cancelled request has no MCP response. Pagination's
`cursor_expired` and `page_shifted` are failure kinds governed by the same
contract and resolver.

Generated Python tool registrations and the TypeScript `MCP_TOOL_HANDLERS`
adapter preserve the normalized envelope as structured content. Outcomes with
`status: "failed"` set the MCP tool result's `isError` flag; `incomplete` outcomes
remain ordinary results with their partial items and failure details intact.
The lower-level `TOOL_HANDLERS` continue to return the normalized envelope for
fixture comparison and custom MCP wiring.

The examples below are generated from the packaged synthetic upstream fixtures
and the Python runtime. Regenerate them with
`python -c 'from mcpforge.failure.docs import regenerate_failure_docs; regenerate_failure_docs()'`.

## Generated MCP tool results

These results come from the generated Python server over FastMCP. A failed
outcome sets `isError: true`; an incomplete outcome carries partial items as a
normal tool result.

### Failed outcome

<!-- failure-example:failed_tool_result:start -->
```json
{
  "content": [
    {
      "text": "{\"status\":\"failed\",\"failure\":{\"kind\":\"malformed\",\"retryable\":false,\"partial_result\":false,\"detail\":\"upstream returned malformed data\"},\"items\":[]}",
      "type": "text"
    }
  ],
  "isError": true,
  "structuredContent": {
    "failure": {
      "detail": "upstream returned malformed data",
      "kind": "malformed",
      "partial_result": false,
      "retryable": false
    },
    "items": [],
    "status": "failed"
  }
}
```
<!-- failure-example:failed_tool_result:end -->

### Incomplete outcome

<!-- failure-example:incomplete_tool_result:start -->
```json
{
  "content": [
    {
      "text": "{\"status\":\"incomplete\",\"failure\":{\"kind\":\"malformed\",\"retryable\":false,\"partial_result\":true,\"detail\":\"upstream returned malformed data\"},\"items\":[{\"id\":1}]}",
      "type": "text"
    }
  ],
  "isError": false,
  "structuredContent": {
    "failure": {
      "detail": "upstream returned malformed data",
      "kind": "malformed",
      "partial_result": true,
      "retryable": false
    },
    "items": [
      {
        "id": 1
      }
    ],
    "status": "incomplete"
  }
}
```
<!-- failure-example:incomplete_tool_result:end -->

## Timeout before the first item

<!-- failure-example:timeout_before_first:start -->
```json
{
  "failure": {
    "detail": "upstream timed out",
    "kind": "timeout",
    "partial_result": false,
    "retryable": true
  },
  "items": [],
  "status": "failed"
}
```
<!-- failure-example:timeout_before_first:end -->

## Malformed upstream response

<!-- failure-example:malformed_invalid_json:start -->
```json
{
  "failure": {
    "detail": "upstream returned malformed data",
    "kind": "malformed",
    "partial_result": false,
    "retryable": false
  },
  "items": [],
  "status": "failed"
}
```
<!-- failure-example:malformed_invalid_json:end -->

## Cancellation before data

<!-- failure-example:cancellation_before_data:start -->
```json
{
  "failure": {
    "detail": "upstream cancelled",
    "kind": "cancelled",
    "partial_result": false,
    "retryable": false
  },
  "items": [],
  "status": "failed"
}
```
<!-- failure-example:cancellation_before_data:end -->

## Partial result followed by timeout

<!-- failure-example:timeout_after_partial:start -->
```json
{
  "failure": {
    "detail": "upstream timed out",
    "kind": "timeout",
    "partial_result": true,
    "retryable": true
  },
  "items": [
    {
      "id": 1,
      "value": "ok"
    }
  ],
  "status": "incomplete"
}
```
<!-- failure-example:timeout_after_partial:end -->
