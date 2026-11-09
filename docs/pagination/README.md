# Pagination contracts

Pagination incompleteness is part of the shared failure contract; see [Failure Semantics](../FAILURE-SEMANTICS.md).

The protocol-level claims here concern MCP list methods: `resources/list`, `tools/list`, `prompts/list`, and `resources/templates/list`. The committed examples test `resources/list` pagination. They make no conformance claim for the other list methods.

Tool-level claims concern upstream traversal performed by `list_records`; tool calls do not inherit MCP list-method pagination semantics. The tools return a shared outcome envelope.

The adapter authenticates opaque cursors and binds them to a collection, effective query, configuration, and traversal id. `TraversalHistory` is process-local and bounded by default to 128 traversals and 10,000 emitted identities per traversal. LRU eviction, identity-bound exhaustion, or a process restart that loses history while retaining the signing key makes continuation fail with `page_shifted`. A fresh process signing key makes an old cursor invalid and returns JSON-RPC `-32602`. Neither case resumes the old traversal: begin a new traversal and do not append its results to an earlier partial result. Retaining the codec key alone does not restore traversal history.

Offset shift detection is bounded: it can detect a change when the adapter observes a missing or changed overlap boundary. Changes outside that observable boundary are not guaranteed to be detected.

## Pattern references

- [cursor](cursor.md)
- [offset](offset.md)
- [page_token](page_token.md)
