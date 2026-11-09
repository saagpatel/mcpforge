# cursor pagination server

Install with `uv pip install .`, then run `pagination-cursor-server` over stdio. For the
bundled test, install pytest separately and run `pytest tests`. FastMCP is the
only direct runtime dependency; the current pagination and outcome runtimes are
vendored. The bundled stable dataset uses page size 3.

`list_records` returns one upstream page with `items`, optional `nextCursor`, and
`outcome`. A complete outcome describes that page read; only absence of
`nextCursor` establishes traversal exhaustion. Failed outcomes set MCP `isError`
while preserving the outcome envelope as structured content. Incomplete outcomes
carry partial data as a normal result.

The same records are readable MCP resources. `resources/list` uses FastMCP's
native list pagination with its cursor wrapped in a separate HMAC codec scoped to
`resources/list`, this pattern, and the server process. `list_records` cursors use
the vendored adapter runtime and bind to the source collection, effective query,
configuration, and traversal history. Both interfaces reject invalid or foreign
cursors with JSON-RPC code -32602. Cursor keys and history are process-local;
restarting the server invalidates old cursors. Cursors are opaque, authenticated,
and not encrypted. This example demonstrates `resources/list` pagination; it
makes no claim about the other MCP list methods or a live upstream.

## Adapter contract

- Cursor validity: Authenticated session cursor bound to collection, query, configuration and traversal; upstream generation must remain valid.
- Ordering guarantee: Strict total order on immutable, comparable (order_key, id_key), with unique ids. The last accepted pair detects regressions; session history detects repeated ids.
- Resume behaviour: Resume after the last key in the current generation, even after expiry.
- Incompleteness detection: Expired generation, duplicate ids, or nonascending items. Session history defaults to 128 traversals (LRU) and 10,000 emitted ids per traversal; configure TraversalHistory and share it via CursorCodec across calls. Missing history after eviction/restart or an exceeded id bound fails explicitly with page_shifted and history unavailable; start a new traversal rather than append a restart. Consumed positions cannot be replayed.
