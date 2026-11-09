"""Provider-independent failure vocabulary and outcome resolution."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import models_json_schema

FailureKind = Literal[
    "timeout", "malformed", "cancelled", "upstream_error", "cursor_expired", "page_shifted"
]

TRANSIENT_KINDS: set[FailureKind] = {"timeout", "upstream_error", "cursor_expired", "page_shifted"}
PAGINATION_KINDS: set[FailureKind] = {"cursor_expired", "page_shifted"}


class FailureContract(BaseModel):
    """The retry and partial-result permissions for one tool."""

    retryable: bool
    partial_result_allowed: bool


class PaginationSpec(BaseModel):
    """The pagination pattern and stable identity keys for one tool."""

    pattern: Literal["cursor", "offset", "page_token"]
    page_size: int = Field(default=50, ge=1, le=1000)
    order_key: str = "id"
    id_key: str = "id"


class Failure(BaseModel):
    """A typed tool failure, including pagination incompleteness."""

    kind: FailureKind
    retryable: bool
    partial_result: bool
    detail: str
    resume_cursor: str | None = None

    @model_validator(mode="after")
    def validate_resume_cursor(self) -> Self:
        if self.resume_cursor is not None and self.kind not in PAGINATION_KINDS:
            raise ValueError("resume_cursor is only valid for pagination failures")
        return self


class ToolOutcome(BaseModel):
    """The common envelope for complete, incomplete, and failed tool results."""

    status: Literal["complete", "incomplete", "failed"]
    failure: Failure | None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status == "complete":
            if self.failure is not None:
                raise ValueError("complete outcomes must not have a failure")
        elif self.failure is None:
            raise ValueError("incomplete and failed outcomes must have a failure")
        elif self.failure.partial_result != (self.status == "incomplete"):
            raise ValueError("partial_result must be true exactly when status is incomplete")
        return self


def resolve_outcome(
    contract: FailureContract,
    kind: FailureKind,
    have_partial: bool,
    detail: str,
    resume_cursor: str | None = None,
) -> ToolOutcome:
    """Resolve a failure using the same rules in every runtime.

    Retryability requires contract.retryable and a kind in TRANSIENT_KINDS;
    malformed and cancelled failures are never retryable. Return incomplete
    with partial_result=True only if the contract allows partial results,
    have_partial is true, and kind is not cancelled. Otherwise return failed
    with partial_result=False. A resume_cursor is valid only for pagination
    failures and is preserved when supplied.
    """
    partial_result = contract.partial_result_allowed and have_partial and kind != "cancelled"
    return ToolOutcome(
        status="incomplete" if partial_result else "failed",
        failure=Failure(
            kind=kind,
            retryable=contract.retryable and kind in TRANSIENT_KINDS,
            partial_result=partial_result,
            detail=detail,
            resume_cursor=resume_cursor,
        ),
    )


def default_contract(tool) -> FailureContract:
    """Derive a tool's default permissions from existing hints and pagination."""
    return FailureContract(
        retryable=tool.retry_safe or bool(tool.idempotent_hint) or bool(tool.read_only_hint),
        partial_result_allowed=tool.pagination is not None,
    )


def contracts_json_schema() -> dict:
    """Export Draft 2020-12 definitions, with ToolOutcome as the root schema.

    FailureContract is available at #/$defs/FailureContract for per-tool use.
    Runtime model validators enforce the additional outcome invariants.
    """
    _, schema = models_json_schema([(ToolOutcome, "validation"), (FailureContract, "validation")])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/$defs/ToolOutcome",
        **schema,
    }
