"""Shared failure and pagination contracts for generated tools."""

from mcpforge.contracts.outcome import (
    PAGINATION_KINDS,
    TRANSIENT_KINDS,
    Failure,
    FailureContract,
    FailureKind,
    PaginationSpec,
    ToolOutcome,
    contracts_json_schema,
    default_contract,
    resolve_outcome,
)

__all__ = [
    "PAGINATION_KINDS",
    "TRANSIENT_KINDS",
    "Failure",
    "FailureContract",
    "FailureKind",
    "PaginationSpec",
    "ToolOutcome",
    "contracts_json_schema",
    "default_contract",
    "resolve_outcome",
]
