"""Tests for mcpforge Pydantic data models."""

import pytest
from pydantic import ValidationError

from mcpforge.models import (
    KNOWN_PACKAGES,
    ResourceDef,
    ServerPlan,
    ToolDef,
    ToolParam,
    ValidationResult,
)


class TestToolParam:
    def test_required_fields(self):
        param = ToolParam(name="count", type="int", description="Number of items")
        assert param.name == "count"
        assert param.type == "int"
        assert param.description == "Number of items"

    def test_defaults(self):
        param = ToolParam(name="x", type="str", description="x")
        assert param.required is True
        assert param.default is None

    def test_optional_param(self):
        param = ToolParam(
            name="limit", type="int", description="limit", required=False, default="10"
        )
        assert param.required is False
        assert param.default == "10"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ToolParam(name="x", description="x")  # type is missing

    def test_roundtrip(self):
        param = ToolParam(
            name="q", type="str | None", description="query", required=False, default="None"
        )
        restored = ToolParam.model_validate(param.model_dump())
        assert restored == param


class TestToolDef:
    def test_basic_construction(self):
        tool = ToolDef(
            name="get_item",
            description="Get an item by ID",
            params=[ToolParam(name="item_id", type="str", description="ID")],
        )
        assert tool.name == "get_item"
        assert len(tool.params) == 1

    def test_defaults(self):
        tool = ToolDef(name="list_items", description="List items", params=[])
        assert tool.return_type == "dict"
        assert tool.is_async is True
        assert tool.error_cases == []

    def test_custom_return_type(self):
        tool = ToolDef(name="list_items", description="List", params=[], return_type="list[dict]")
        assert tool.return_type == "list[dict]"

    def test_error_cases(self):
        tool = ToolDef(
            name="get_item",
            description="Get item",
            params=[],
            error_cases=["not found", "invalid id"],
        )
        assert len(tool.error_cases) == 2

    def test_roundtrip(self):
        tool = ToolDef(
            name="delete_item",
            description="Delete item",
            params=[ToolParam(name="id", type="str", description="ID")],
            error_cases=["not found"],
        )
        restored = ToolDef.model_validate(tool.model_dump())
        assert restored == tool


class TestResourceDef:
    def test_basic_construction(self):
        res = ResourceDef(
            uri_pattern="file://{path}",
            name="File",
            description="A local file resource",
        )
        assert res.uri_pattern == "file://{path}"
        assert res.is_template is False

    def test_template_resource(self):
        res = ResourceDef(
            uri_pattern="db://records/{id}",
            name="Record",
            description="A database record",
            is_template=True,
        )
        assert res.is_template is True

    def test_roundtrip(self):
        res = ResourceDef(uri_pattern="x://y", name="Y", description="desc", is_template=True)
        restored = ResourceDef.model_validate(res.model_dump())
        assert restored == res


class TestServerPlan:
    def _minimal_plan(self, **kwargs) -> ServerPlan:
        defaults = {
            "name": "Test Server",
            "description": "A test server",
            "tools": [],
        }
        return ServerPlan(**{**defaults, **kwargs})

    def test_basic_construction(self):
        plan = self._minimal_plan()
        assert plan.name == "Test Server"
        assert plan.version == "0.1.0"
        assert plan.transport == "streamable-http"

    def test_slug_auto_derived_from_name(self):
        plan = self._minimal_plan(name="My Cool Server")
        assert plan.slug == "my-cool-server"

    def test_slug_auto_derived_with_underscores(self):
        plan = self._minimal_plan(name="my_server")
        assert plan.slug == "my-server"

    def test_explicit_slug_not_overwritten(self):
        plan = self._minimal_plan(name="My Server", slug="custom-slug")
        assert plan.slug == "custom-slug"

    def test_defaults(self):
        plan = self._minimal_plan()
        assert plan.resources == []
        assert plan.env_vars == []
        assert plan.external_packages == []

    def test_with_tools(self):
        tool = ToolDef(
            name="do_thing",
            description="Does a thing",
            params=[ToolParam(name="x", type="str", description="x")],
        )
        plan = self._minimal_plan(tools=[tool])
        assert len(plan.tools) == 1
        assert plan.tools[0].name == "do_thing"

    def test_with_env_vars(self):
        plan = self._minimal_plan(env_vars=["API_KEY", "DATABASE_URL"])
        assert "API_KEY" in plan.env_vars

    def test_transport_override(self):
        plan = self._minimal_plan(transport="stdio")
        assert plan.transport == "stdio"

    def test_slug_sanitizes_path_traversal(self):
        plan = self._minimal_plan(name="../../evil-dir")
        assert ".." not in plan.slug
        assert "/" not in plan.slug

    def test_slug_sanitizes_special_chars(self):
        plan = self._minimal_plan(name="My Server! (v2)")
        assert plan.slug == "my-server-v2"

    def test_invalid_external_package_raises(self):
        with pytest.raises(ValidationError):
            self._minimal_plan(external_packages=["../../../evil; rm -rf /"])

    def test_valid_external_packages_accepted(self):
        plan = self._minimal_plan(external_packages=["httpx", "pydantic", "my-pkg.extra"])
        assert len(plan.external_packages) == 3

    def test_invalid_env_var_raises(self):
        with pytest.raises(ValidationError):
            self._minimal_plan(env_vars=["../../SECRET"])

    def test_valid_env_vars_accepted(self):
        plan = self._minimal_plan(env_vars=["API_KEY", "DATABASE_URL", "MY_VAR_123"])
        assert len(plan.env_vars) == 3

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ServerPlan(description="desc", tools=[])  # name missing

    def test_roundtrip(self):
        plan = self._minimal_plan(
            name="Round Trip Server",
            env_vars=["KEY"],
            external_packages=["httpx"],
        )
        restored = ServerPlan.model_validate(plan.model_dump())
        assert restored.name == plan.name
        assert restored.slug == plan.slug
        assert restored.env_vars == plan.env_vars


class TestValidationResult:
    def test_defaults(self):
        result = ValidationResult()
        assert result.syntax_ok is False
        assert result.import_ok is False
        assert result.lint_errors == []
        assert result.tests_run == 0
        assert result.is_valid is False

    def test_is_valid_when_all_structural_checks_pass(self):
        result = ValidationResult(syntax_ok=True, import_ok=True)
        assert result.is_valid is True

    def test_is_valid_false_when_syntax_fails(self):
        result = ValidationResult(syntax_ok=False, import_ok=True)
        assert result.is_valid is False

    def test_is_valid_false_when_import_fails(self):
        result = ValidationResult(syntax_ok=True, import_ok=False)
        assert result.is_valid is False

    def test_is_valid_false_when_lint_errors(self):
        result = ValidationResult(syntax_ok=True, import_ok=True, lint_errors=["E501"])
        assert result.is_valid is False

    def test_is_valid_excludes_tests_passed(self):
        """is_valid should not require tests_passed — external API servers may fail tests."""
        result = ValidationResult(syntax_ok=True, import_ok=True, tests_passed=False)
        assert result.is_valid is True

    def test_roundtrip(self):
        result = ValidationResult(
            syntax_ok=True,
            import_ok=True,
            tests_passed=True,
            tests_run=5,
            test_output="5 passed",
        )
        restored = ValidationResult.model_validate(result.model_dump())
        assert restored.tests_run == 5
        assert restored.is_valid is True


class TestResourceDefValidation:
    def test_valid_uri_pattern_accepted(self):
        r = ResourceDef(uri_pattern="file:///{path}", name="File", description="A file")
        assert r.uri_pattern == "file:///{path}"

    def test_valid_custom_scheme_accepted(self):
        r = ResourceDef(uri_pattern="docs://{doc_id}/content", name="Doc", description="Doc")
        assert r.uri_pattern.startswith("docs://")

    def test_missing_scheme_rejected(self):
        with pytest.raises(ValidationError):
            ResourceDef(uri_pattern="no-scheme/path", name="Bad", description="Bad")

    def test_bare_path_rejected(self):
        with pytest.raises(ValidationError):
            ResourceDef(uri_pattern="/just/a/path", name="Bad", description="Bad")


class TestKnownPackages:
    def test_known_packages_is_nonempty(self):
        assert len(KNOWN_PACKAGES) > 30

    def test_check_unknown_packages_returns_unknown(self):
        unknown = ServerPlan.check_unknown_packages(["httpx", "totally-fake-pkg"])
        assert unknown == ["totally-fake-pkg"]

    def test_check_unknown_packages_all_known(self):
        unknown = ServerPlan.check_unknown_packages(["httpx", "redis", "pydantic"])
        assert unknown == []
