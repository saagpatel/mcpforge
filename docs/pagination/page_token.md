# page_token pagination

## Adapter contract

- Cursor validity: Authenticated session cursor bound to collection, query, configuration and traversal; upstream token bound to snapshot version.
- Ordering guarantee: Strict total snapshot order on immutable, comparable (order_key, id_key), with unique ids. The last accepted pair detects regressions; session history detects repeated ids.
- Resume behaviour: Expiry/version change starts a NEW traversal; do not append to partials.
- Incompleteness detection: Expired token, version change, duplicates, or order regression. Session history defaults to 128 traversals (LRU) and 10,000 emitted ids per traversal; configure TraversalHistory and share it via CursorCodec across calls. Missing history after eviction/restart or an exceeded id bound fails explicitly with page_shifted and history unavailable; start a new traversal rather than append a restart. Consumed positions cannot be replayed.

## Observed behaviour

These blocks come from the deterministic synthetic upstream harness. Opaque session cursors are replaced by a placeholder so regeneration is byte-stable.

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
      "resume_cursor": "<opaque session cursor omitted>",
      "retryable": true
    },
    "status": "incomplete"
  }
}
```
<!-- pagination-example:page_token-incomplete:end -->
