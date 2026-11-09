# offset pagination server

Install with `uv pip install .`, then run `pagination-offset-server`
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

# offset pagination

## Adapter contract

- Cursor validity: Authenticated session cursor with an unchanged overlap boundary.
- Ordering guarantee: Ascending immutable (order_key, id_key), verified on every page.
- Resume behaviour: Restart traversal if the overlap boundary cannot be found.
- Incompleteness detection: Fetch offset-1 with limit+1; locate the unchanged last item and discard overlap. A shift is detected only when it changes an observable overlap boundary; a missing or changed boundary, duplicate ids, or order regression means page_shifted.
- Contract defaults: retryable follows retry_safe, idempotent_hint, or read_only_hint; partial_result_allowed is true for pagination tools.

## Observed behaviour

### Stable traversal (`09-offset-stable`)

<!-- pagination-example:offset-stable:start -->
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
<!-- pagination-example:offset-stable:end -->

### Mutation that recovers (`10-offset-insert-before-cursor`)

<!-- pagination-example:offset-recovery:start -->
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
<!-- pagination-example:offset-recovery:end -->

### Mutation that ends incomplete (`12-offset-delete-before-cursor`)

<!-- pagination-example:offset-incomplete:start -->
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
      "detail": "offset boundary cannot be safely located",
      "kind": "page_shifted",
      "partial_result": true,
      "resume_cursor": null,
      "retryable": true
    },
    "status": "incomplete"
  }
}
```
<!-- pagination-example:offset-incomplete:end -->
