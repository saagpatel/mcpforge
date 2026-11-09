# cursor pagination

## Adapter contract

- Cursor validity: Authenticated session cursor bound to collection, query, configuration and traversal; upstream generation must remain valid.
- Ordering guarantee: Strict total order on immutable, comparable (order_key, id_key), with unique ids. The last accepted pair detects regressions; session history detects repeated ids.
- Resume behaviour: Resume after the last key in the current generation, even after expiry.
- Incompleteness detection: Expired generation, duplicate ids, or nonascending items. Session history defaults to 128 traversals (LRU) and 10,000 emitted ids per traversal; configure TraversalHistory and share it via CursorCodec across calls. Missing history after eviction/restart or an exceeded id bound fails explicitly with page_shifted and history unavailable; start a new traversal rather than append a restart. Consumed positions cannot be replayed.

## Observed behaviour

These blocks come from the deterministic synthetic upstream harness. Opaque session cursors are replaced by a placeholder so regeneration is byte-stable.

### Stable traversal (`01-cursor-stable`)

<!-- pagination-example:cursor-stable:start -->
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
<!-- pagination-example:cursor-stable:end -->

### Mutation that recovers (`02-cursor-insert-before-cursor`)

<!-- pagination-example:cursor-recovery:start -->
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
<!-- pagination-example:cursor-recovery:end -->

### Mutation that ends incomplete (`07-cursor-expired-cursor`)

<!-- pagination-example:cursor-incomplete:start -->
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
      "detail": "keyset generation expired",
      "kind": "cursor_expired",
      "partial_result": true,
      "resume_cursor": "<opaque session cursor omitted>",
      "retryable": true
    },
    "status": "incomplete"
  }
}
```
<!-- pagination-example:cursor-incomplete:end -->
