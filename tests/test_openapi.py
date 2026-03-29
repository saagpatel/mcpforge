"""Tests for the openapi module."""

import json
from pathlib import Path

import pytest
import yaml

from mcpforge.openapi import load_spec, parse_openapi

SAMPLE_SPEC: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0", "description": "A pet store API"},
    "servers": [{"url": "https://petstore.example.com"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "list_pets",
                "summary": "List all pets",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"type": "array"}}
                        },
                    }
                },
            },
            "post": {
                "operationId": "create_pet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/pets/{id}": {
            "get": {
                "operationId": "get_pet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {"name": "id", "in": "path", "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "ok"}},
            }
        },
    },
}


def test_parse_openapi_extracts_correct_tool_count() -> None:
    """parse_openapi extracts 3 tools from the sample spec."""
    plan = parse_openapi(SAMPLE_SPEC)
    assert len(plan.tools) == 3


def test_parse_openapi_tool_names_are_snake_cased() -> None:
    """Tool names are snake_cased from operationId."""
    plan = parse_openapi(SAMPLE_SPEC)
    names = {t.name for t in plan.tools}
    assert names == {"list_pets", "create_pet", "get_pet"}


def test_parse_openapi_parameter_types() -> None:
    """Parameters map to correct Python types."""
    plan = parse_openapi(SAMPLE_SPEC)
    list_pets = next(t for t in plan.tools if t.name == "list_pets")
    limit_param = next(p for p in list_pets.params if p.name == "limit")
    assert limit_param.type == "int"

    get_pet = next(t for t in plan.tools if t.name == "get_pet")
    id_param = next(p for p in get_pet.params if p.name == "id")
    assert id_param.type == "str"


def test_parse_openapi_base_url_in_env_vars() -> None:
    """servers[0].url adds BASE_URL to env_vars."""
    plan = parse_openapi(SAMPLE_SPEC)
    assert "BASE_URL" in plan.env_vars


def test_parse_openapi_request_body_adds_body_param() -> None:
    """requestBody adds a body: dict param."""
    plan = parse_openapi(SAMPLE_SPEC)
    create_pet = next(t for t in plan.tools if t.name == "create_pet")
    param_names = [p.name for p in create_pet.params]
    assert "body" in param_names
    body_param = next(p for p in create_pet.params if p.name == "body")
    assert body_param.type == "dict"


def test_parse_openapi_raises_for_empty_paths() -> None:
    """parse_openapi raises ValueError when paths is empty."""
    spec = {**SAMPLE_SPEC, "paths": {}}
    with pytest.raises(ValueError, match="no paths"):
        parse_openapi(spec)


def test_parse_openapi_raises_for_swagger_2x() -> None:
    """parse_openapi raises ValueError for OpenAPI 2.x (swagger) specs."""
    spec = {k: v for k, v in SAMPLE_SPEC.items() if k != "openapi"}
    spec["swagger"] = "2.0"
    with pytest.raises(ValueError, match="OpenAPI 3.x"):
        parse_openapi(spec)


def test_load_spec_loads_json(tmp_path: Path) -> None:
    """load_spec loads a JSON file correctly."""
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(SAMPLE_SPEC), encoding="utf-8")
    loaded = load_spec(spec_file)
    assert loaded["info"]["title"] == "Pet Store"


def test_load_spec_loads_yaml(tmp_path: Path) -> None:
    """load_spec loads a YAML file correctly."""
    minimal_spec = {
        "openapi": "3.0.0",
        "info": {"title": "YAML Server", "version": "1.0"},
        "paths": {
            "/hello": {
                "get": {
                    "operationId": "say_hello",
                    "summary": "Say hello",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml.dump(minimal_spec), encoding="utf-8")
    loaded = load_spec(spec_file)
    assert loaded["info"]["title"] == "YAML Server"


def test_parse_openapi_server_name_from_title() -> None:
    """parse_openapi sets server name from spec info.title."""
    plan = parse_openapi(SAMPLE_SPEC)
    assert plan.name == "Pet Store"


def test_parse_openapi_list_operation_return_type() -> None:
    """list operation with array response has list[dict] return_type."""
    plan = parse_openapi(SAMPLE_SPEC)
    list_pets = next(t for t in plan.tools if t.name == "list_pets")
    assert list_pets.return_type == "list[dict]"


def test_parse_openapi_description_from_info() -> None:
    """parse_openapi uses info.description as server description."""
    plan = parse_openapi(SAMPLE_SPEC)
    assert plan.description == "A pet store API"
