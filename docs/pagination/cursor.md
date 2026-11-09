# cursor pagination

## Adapter contract

- Cursor validity: Authenticated session cursor; upstream generation must remain valid.
- Ordering guarantee: Ascending (order_key, id_key); keys must be immutable and comparable.
- Resume behaviour: Resume after the last key in the current generation, even after expiry.
- Incompleteness detection: Expired generation, duplicate ids, or nonascending items.
- Contract defaults: retryable follows retry_safe, idempotent_hint, or read_only_hint; partial_result_allowed is true for pagination tools.

## Observed behaviour

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
      "resume_cursor": "eyJzdGF0ZSI6eyJjb25maWd1cmF0aW9uIjpbMywiaWQiLCJvcmRlciJdLCJwYXR0ZXJuIjoiY3Vyc29yIiwicG9zaXRpb24iOnsiYWZ0ZXIiOlszMCwzMF0sImdlbmVyYXRpb24iOm51bGx9fSwidmVyc2lvbiI6MX0.XV4bnH9cAeY0KxIJTPhvJqmkXTDVXc6b7C-SVudWoFw",
      "retryable": true
    },
    "status": "incomplete"
  }
}
```
<!-- pagination-example:cursor-incomplete:end -->
