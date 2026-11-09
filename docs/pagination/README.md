# Pagination contracts

Pagination incompleteness is a case of the shared failure contract; see [Failure Semantics](../FAILURE-SEMANTICS.md).

The protocol-level claims below apply to MCP list methods: `resources/list`, `tools/list`, `prompts/list`, and `resources/templates/list`. Tool-level claims describe upstream traversal performed by `list_records`; tool calls do not inherit MCP list-method pagination semantics.

The example servers use FastMCP's native `resources/list` pagination and wrap its continuation state in the pagination HMAC cursor codec. Their `list_records` tools traverse the bundled synthetic upstream and return an outcome envelope; absence of `nextCursor` marks tool traversal exhaustion.

Installed-server protocol conformance tests cover `resources/list`; these examples make no conformance claim for the other list methods.

Offset shift detection is bounded: it is guaranteed only when the change affects an overlap boundary the adapter can observe.

## Pattern references

- [cursor](cursor.md)
- [offset](offset.md)
- [page_token](page_token.md)
