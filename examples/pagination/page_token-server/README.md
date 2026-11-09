# page_token pagination server

Install with `uv pip install .`, then run `pagination-page-token-server`
over stdio. For the bundled test, install pytest and run `pytest tests`.
Only FastMCP is a direct runtime dependency; adapters and contracts are vendored.
The bundled stable dataset uses page size 3.

`list_records` returns one upstream page with `items`, optional `nextCursor`, and
`outcome`. A complete outcome describes that page read; only absence of
`nextCursor` establishes traversal exhaustion. Failed outcomes set `isError`;
incomplete outcomes carry partial data as a normal result.

The same records are readable MCP resources. `resources/list` uses FastMCP's
native list pagination with its cursor wrapped in the vendored HMAC codec.
Both interfaces reject invalid cursors with JSON-RPC code -32602. Keys last for
one server process; cursors are opaque, authenticated, and not encrypted.
Tool and resource cursors cannot be interchanged. This example covers
`resources/list`, not all MCP list methods or a live upstream.

# page_token pagination

## Adapter contract

- Cursor validity: Session cursor; upstream token bound to snapshot version.
- Ordering guarantee: Snapshot order is ascending immutable (order_key, id_key).
- Resume behaviour: Expiry/version change starts a NEW traversal; do not append to partials.
- Incompleteness detection: Expired token, version change, duplicates, or order regression.
- Contract defaults: retryable follows retry_safe, idempotent_hint, or read_only_hint; partial_result_allowed is true for pagination tools.

## Observed behaviour

### Stable traversal (`17-page_token-stable`)

<!-- pagination-example:page_token-stable:start -->
```json
{
  "items": [
    {
      "id": 10,
      "order": 10
    },
    {
      "id": 20,
      "order": 20
    },
    {
      "id": 30,
      "order": 30
    },
    {
      "id": 40,
      "order": 40
    },
    {
      "id": 50,
      "order": 50
    },
    {
      "id": 60,
      "order": 60
    },
    {
      "id": 70,
      "order": 70
    },
    {
      "id": 80,
      "order": 80
    }
  ],
  "outcome": {
    "failure": null,
    "status": "complete"
  }
}
```
<!-- pagination-example:page_token-stable:end -->

### Mutation that recovers (`18-page_token-insert-before-cursor`)

<!-- pagination-example:page_token-recovery:start -->
```json
{
  "items": [
    {
      "id": 10,
      "order": 10
    },
    {
      "id": 20,
      "order": 20
    },
    {
      "id": 30,
      "order": 30
    },
    {
      "id": 40,
      "order": 40
    },
    {
      "id": 50,
      "order": 50
    },
    {
      "id": 60,
      "order": 60
    },
    {
      "id": 70,
      "order": 70
    },
    {
      "id": 80,
      "order": 80
    }
  ],
  "outcome": {
    "failure": null,
    "status": "complete"
  }
}
```
<!-- pagination-example:page_token-recovery:end -->

### Mutation that ends incomplete (`23-page_token-expired-cursor`)

<!-- pagination-example:page_token-incomplete:start -->
```json
{
  "items": [
    {
      "id": 10,
      "order": 10
    },
    {
      "id": 20,
      "order": 20
    },
    {
      "id": 30,
      "order": 30
    }
  ],
  "outcome": {
    "failure": {
      "detail": "snapshot token expired",
      "kind": "cursor_expired",
      "partial_result": true,
      "resume_cursor": "eyJzdGF0ZSI6eyJjb25maWd1cmF0aW9uIjpbMywiaWQiLCJvcmRlciJdLCJwYXR0ZXJuIjoicGFnZV90b2tlbiIsInBvc2l0aW9uIjp7InRva2VuIjpudWxsLCJ2ZXJzaW9uIjpudWxsfX0sInZlcnNpb24iOjF9.QAqR_Dy6VDVMzZzDZYx65mGtqVAbfe8DQkXoCUzjAFg",
      "retryable": true
    },
    "status": "incomplete"
  }
}
```
<!-- pagination-example:page_token-incomplete:end -->
