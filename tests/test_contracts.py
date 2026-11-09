"""Shared failure contracts, legacy serialization, and pagination inference."""

import json
from itertools import product
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from mcpforge.contracts import (
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
from mcpforge.models import ServerPlan, ToolDef
from mcpforge.openapi import parse_openapi
from tests.fixtures.sample_plans import WEATHER_PLAN

# Captured from the existing WEATHER_PLAN fixture using the pre-contract ToolDef.
LEGACY_WEATHER_JSON = (
    '{"name":"Weather Service","slug":"weather-service","description":"An MCP server for '
    'fetching current weather and forecasts via OpenWeatherMap.","version":"0.1.0","tools":[{'
    '"name":"get_current_weather","description":"Get current weather conditions for a '
    'city.","params":[{"name":"city","type":"str","description":"City name","required":true,"'
    'default":null,"location":null,"media_type":null}],"return_type":"dict","is_async":true,"'
    'error_cases":["city not found","API key missing or invalid"],"tags":[],"method":null,"pa'
    'th":null,"auth":null,"auth_scheme":null,"auth_env_var":null,"auth_location":null,"auth_p'
    'arameter_name":null,"retry_safe":false,"permissions":[],"auth_scopes":[],"data_zones":[]'
    ',"egress_destinations":[],"read_only_hint":null,"destructive_hint":null,"idempotent_hint'
    '":null,"open_world_hint":null},{"name":"get_forecast","description":"Get a 7-day weather'
    ' forecast for a city.","params":[{"name":"city","type":"str","description":"City name","'
    'required":true,"default":null,"location":null,"media_type":null},{"name":"days","type":"'
    'int","description":"Number of forecast days (1-7)","required":false,"default":"7","locat'
    'ion":null,"media_type":null}],"return_type":"list[dict]","is_async":true,"error_cases":['
    '"city not found","days must be between 1 and 7"],"tags":[],"method":null,"path":null,"au'
    'th":null,"auth_scheme":null,"auth_env_var":null,"auth_location":null,"auth_parameter_nam'
    'e":null,"retry_safe":false,"permissions":[],"auth_scopes":[],"data_zones":[],"egress_des'
    'tinations":[],"read_only_hint":null,"destructive_hint":null,"idempotent_hint":null,"open'
    '_world_hint":null}],"resources":[],"prompts":[],"env_vars":["OPENWEATHER_API_KEY"],"exte'
    'rnal_packages":["httpx"],"transport":"streamable-http","auth":null,"auth_profile":null,"'
    'middleware_profiles":[],"openapi_metadata":{}}'
)


@pytest.mark.parametrize("retryable", [False, True], ids=["no-retry", "retry"])
@pytest.mark.parametrize(
    ("allow_partial", "have_partial", "index"),
    [(False, False, 0), (False, True, 1), (True, False, 2), (True, True, 3)],
    ids=["disallowed-empty", "disallowed-partial", "allowed-empty", "allowed-partial"],
)
@pytest.mark.parametrize(
    ("kind", "transient", "statuses"),
    [
        ("timeout", True, ("failed", "failed", "failed", "incomplete")),
        ("malformed", False, ("failed", "failed", "failed", "incomplete")),
        ("cancelled", False, ("failed", "failed", "failed", "failed")),
        ("upstream_error", True, ("failed", "failed", "failed", "incomplete")),
        ("cursor_expired", True, ("failed", "failed", "failed", "incomplete")),
        ("page_shifted", True, ("failed", "failed", "failed", "incomplete")),
    ],
    ids=list(get_args(FailureKind)),
)
def test_resolve_outcome_every_row(
    kind: FailureKind,
    transient: bool,
    statuses: tuple[str, ...],
    allow_partial: bool,
    have_partial: bool,
    index: int,
    retryable: bool,
) -> None:
    outcome = resolve_outcome(
        FailureContract(retryable=retryable, partial_result_allowed=allow_partial),
        kind,
        have_partial,
        "Interrupted request",
    )
    assert outcome.status == statuses[index]
    assert outcome.failure is not None
    assert outcome.failure.model_dump() == {
        "kind": kind,
        "retryable": transient if retryable else False,
        "partial_result": statuses[index] == "incomplete",
        "detail": "Interrupted request",
        "resume_cursor": None,
    }


@pytest.mark.parametrize("status", ["complete", "incomplete", "failed"])
@pytest.mark.parametrize("partial_result", [None, False, True])
def test_envelope_invariants(status: str, partial_result: bool | None) -> None:
    failure = (
        None
        if partial_result is None
        else {
            "kind": "timeout",
            "retryable": True,
            "partial_result": partial_result,
            "detail": "Timed out",
        }
    )
    valid = (status, partial_result) in {
        ("complete", None),
        ("incomplete", True),
        ("failed", False),
    }
    data = {"status": status, "failure": failure}
    if valid:
        outcome = ToolOutcome.model_validate(data)
        assert ToolOutcome.model_validate_json(outcome.model_dump_json()) == outcome
    else:
        with pytest.raises(ValidationError):
            ToolOutcome.model_validate(data)
        with pytest.raises(ValidationError):
            ToolOutcome.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("kind", get_args(FailureKind))
@pytest.mark.parametrize("allow_partial", [False, True])
def test_resume_cursor_is_pagination_only(kind: FailureKind, allow_partial: bool) -> None:
    contract = FailureContract(retryable=True, partial_result_allowed=allow_partial)
    if kind in {"cursor_expired", "page_shifted"}:
        outcome = resolve_outcome(contract, kind, True, "Pagination interrupted", "next-42")
        assert outcome.failure.resume_cursor == "next-42"
        assert outcome.status == ("incomplete" if allow_partial else "failed")
    else:
        with pytest.raises(ValidationError, match="only valid for pagination"):
            resolve_outcome(contract, kind, True, "Interrupted", "next-42")


def test_vocabulary_and_required_fields() -> None:
    assert set(get_args(FailureKind)) == {
        "timeout",
        "malformed",
        "cancelled",
        "upstream_error",
        "cursor_expired",
        "page_shifted",
    }
    assert TRANSIENT_KINDS == {"timeout", "upstream_error", "cursor_expired", "page_shifted"}
    assert PAGINATION_KINDS == {"cursor_expired", "page_shifted"}
    assert set(FailureContract.model_fields) == {"retryable", "partial_result_allowed"}
    with pytest.raises(ValidationError):
        FailureContract.model_validate({"retryable": True})
    with pytest.raises(ValidationError):
        Failure(kind="other", retryable=False, partial_result=False, detail="Unknown")
    with pytest.raises(ValidationError):
        ToolOutcome.model_validate({"status": "other", "failure": None})


@pytest.mark.parametrize(
    ("retry_safe", "idempotent_hint", "read_only_hint"),
    list(product([False, True], [None, False, True], [None, False, True])),
)
@pytest.mark.parametrize("paginated", [False, True])
def test_default_contract_derivation(
    retry_safe: bool, idempotent_hint: bool | None, read_only_hint: bool | None, paginated: bool
) -> None:
    tool = ToolDef(
        name="list_items",
        description="List items",
        params=[],
        retry_safe=retry_safe,
        idempotent_hint=idempotent_hint,
        read_only_hint=read_only_hint,
        pagination=PaginationSpec(pattern="cursor") if paginated else None,
    )
    assert default_contract(tool) == FailureContract(
        retryable=any(value is True for value in (retry_safe, idempotent_hint, read_only_hint)),
        partial_result_allowed=paginated,
    )


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_pagination_defaults(pattern: str) -> None:
    spec = PaginationSpec.model_validate({"pattern": pattern})
    assert spec.model_dump() == {
        "pattern": pattern,
        "page_size": 50,
        "order_key": "id",
        "id_key": "id",
    }


@pytest.mark.parametrize("page_size", [1, 1000])
def test_pagination_page_size_boundaries(page_size: int) -> None:
    assert PaginationSpec(pattern="cursor", page_size=page_size).page_size == page_size


@pytest.mark.parametrize("page_size", [0, -1, 1001])
def test_pagination_rejects_out_of_bounds_page_size(page_size: int) -> None:
    with pytest.raises(ValidationError):
        PaginationSpec(pattern="cursor", page_size=page_size)


def test_pagination_rejects_unknown_pattern() -> None:
    with pytest.raises(ValidationError):
        PaginationSpec.model_validate({"pattern": "unknown"})


def test_schema_file_matches_export() -> None:
    schema = contracts_json_schema()
    checked_in = Path(__file__).parents[1] / "src/mcpforge/contracts/outcome.schema.json"
    assert json.loads(checked_in.read_text(encoding="utf-8")) == schema
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$ref"] == "#/$defs/ToolOutcome"
    assert set(schema["$defs"]) == {"ToolOutcome", "Failure", "FailureContract"}
    outcome_schema = ToolOutcome.model_json_schema()
    assert schema["$defs"]["ToolOutcome"] == {
        key: value for key, value in outcome_schema.items() if key != "$defs"
    }
    assert set(schema["$defs"]["FailureContract"]["properties"]) == {
        "retryable",
        "partial_result_allowed",
    }


def test_legacy_plan_serialization_is_byte_identical() -> None:
    assert WEATHER_PLAN.model_dump_json() == LEGACY_WEATHER_JSON
    expected = json.loads(LEGACY_WEATHER_JSON)
    assert WEATHER_PLAN.model_dump() == expected
    assert json.dumps(WEATHER_PLAN.model_dump()) == json.dumps(expected)
    restored = ServerPlan.model_validate_json(LEGACY_WEATHER_JSON)
    assert restored.model_dump_json() == LEGACY_WEATHER_JSON
    for tool, legacy_tool in zip(restored.tools, expected["tools"], strict=True):
        assert tool.failure_contract is None
        assert tool.pagination is None
        assert tool.model_dump() == legacy_tool
        assert tool.model_dump_json() == json.dumps(legacy_tool, separators=(",", ":"))
        assert tool.model_dump(include={"auth", "failure_contract", "pagination"}) == {"auth": None}


@pytest.mark.parametrize("contract_set", [False, True])
@pytest.mark.parametrize("pagination_set", [False, True])
def test_new_fields_serialize_only_when_set(contract_set: bool, pagination_set: bool) -> None:
    tool = ToolDef(
        name="items",
        description="Items",
        params=[],
        failure_contract=(
            FailureContract(retryable=True, partial_result_allowed=True) if contract_set else None
        ),
        pagination=PaginationSpec(pattern="cursor") if pagination_set else None,
    )
    for dump in (tool.model_dump(), json.loads(tool.model_dump_json())):
        assert ("failure_contract" in dump) == contract_set
        assert ("pagination" in dump) == pagination_set
        assert ToolDef.model_validate(dump) == tool
    plan = ServerPlan(name="Items", description="Items", tools=[tool])
    assert ServerPlan.model_validate_json(plan.model_dump_json()) == plan


@pytest.mark.parametrize(
    ("names", "pattern"),
    [
        (["cursor"], "cursor"),
        (["next_cursor"], "cursor"),
        (["after"], "cursor"),
        (["before"], "cursor"),
        (["before", "after", "limit"], "cursor"),
        (["cursor", "limit"], "cursor"),
        (["page_token"], "page_token"),
        (["page_token", "limit"], "page_token"),
        (["offset"], "offset"),
        (["offset", "limit"], "offset"),
        (["page", "per_page"], "offset"),
        ([], None),
        (["limit"], None),
        (["page"], None),
        (["per_page"], None),
        (["cursor", "offset", "limit"], None),
        (["cursor", "page_token"], None),
        (["page_token", "page", "per_page"], None),
        (["cursor", "page"], None),
        (["page_token", "offset"], None),
    ],
    ids=lambda value: "+".join(value) or "no-params" if isinstance(value, list) else str(value),
)
def test_openapi_pagination_mapping(names: list[str], pattern: str | None) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Items"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "parameters": [{"name": name, "in": "query"} for name in names],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    plan = parse_openapi(spec)
    tool = plan.tools[0]
    if pattern is None:
        assert tool.pagination is None
        assert "pagination" not in tool.model_dump()
    else:
        assert tool.pagination == PaginationSpec.model_validate({"pattern": pattern})
    assert tool.failure_contract is None
    assert plan.openapi_metadata == {
        "source": "openapi",
        "tags": [],
        "security_schemes": [],
        "servers": [],
    }
    if names:
        assert f"Pagination parameters: {', '.join(names)}." in tool.description


def test_openapi_pagination_only_uses_query_parameters() -> None:
    plan = parse_openapi(
        {
            "openapi": "3.0.0",
            "info": {"title": "Items"},
            "paths": {
                "/items/{cursor}": {
                    "parameters": [{"name": "cursor", "in": "path"}],
                    "get": {"parameters": [{"name": "page_token", "in": "header"}]},
                }
            },
        }
    )
    assert plan.tools[0].pagination is None


def test_openapi_inherits_pagination_parameters() -> None:
    plan = parse_openapi(
        {
            "openapi": "3.0.0",
            "info": {"title": "Items"},
            "paths": {
                "/items": {
                    "parameters": [{"name": "page", "in": "query"}],
                    "get": {"parameters": [{"name": "per_page", "in": "query"}]},
                }
            },
        }
    )
    assert plan.tools[0].pagination == PaginationSpec(pattern="offset")
