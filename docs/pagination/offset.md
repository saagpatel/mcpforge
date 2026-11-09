# offset pagination

## Adapter contract

- Cursor validity: Authenticated session cursor bound to collection, query, configuration and traversal with an unchanged overlap boundary.
- Ordering guarantee: Strict total order on immutable, comparable (order_key, id_key), with unique ids. The last accepted pair detects regressions; session history detects repeated ids.
- Resume behaviour: Restart traversal if the overlap boundary cannot be found.
- Incompleteness detection: Fetch offset-1 with limit+1; locate the unchanged last item and discard overlap. Missing or changed boundary, duplicate ids, or order regression means page_shifted. Session history defaults to 128 traversals (LRU) and 10,000 emitted ids per traversal; configure TraversalHistory and share it via CursorCodec across calls. Missing history after eviction/restart or an exceeded id bound fails explicitly with page_shifted and history unavailable; start a new traversal rather than append a restart. Consumed positions cannot be replayed.

## Observed behaviour

These blocks come from the deterministic synthetic upstream harness. Opaque session cursors are replaced by a placeholder so regeneration is byte-stable.

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
