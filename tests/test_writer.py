"""Tests for mcpforge writer module."""

import json

import pytest

from mcpforge.models import ServerPlan, ToolDef, ToolParam
from mcpforge.writer import _validate_rel_path, write_server, write_server_multi


def _sample_plan(**kwargs) -> ServerPlan:
    defaults = {
        "name": "Todo Manager",
        "slug": "todo-manager",
        "description": "A server for managing TODO items",
        "version": "0.1.0",
        "tools": [
            ToolDef(
                name="create_todo",
                description="Create a todo",
                params=[ToolParam(name="title", type="str", description="Title")],
            )
        ],
        "env_vars": [],
        "external_packages": [],
    }
    return ServerPlan(**{**defaults, **kwargs})


class TestWriteServer:
    def test_creates_all_five_files(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "server code", "test code", out)
        assert (out / "server.py").exists()
        assert (out / "test_server.py").exists()
        assert (out / "pyproject.toml").exists()
        assert (out / "README.md").exists()
        assert (out / "config.json").exists()

    def test_server_py_contains_provided_code(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "MY UNIQUE SERVER CODE", "test code", out)
        assert "MY UNIQUE SERVER CODE" in (out / "server.py").read_text()

    def test_test_server_py_contains_provided_code(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "server code", "MY UNIQUE TEST CODE", out)
        assert "MY UNIQUE TEST CODE" in (out / "test_server.py").read_text()

    def test_pyproject_toml_contains_slug(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "pyproject.toml").read_text()
        assert "todo-manager" in content

    def test_pyproject_toml_contains_version(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "pyproject.toml").read_text()
        assert "0.1.0" in content

    def test_pyproject_toml_contains_fastmcp_dependency(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "pyproject.toml").read_text()
        assert "fastmcp>=3.1.0" in content

    def test_pyproject_toml_testpaths_is_dot(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "pyproject.toml").read_text()
        assert 'testpaths = ["."]' in content

    def test_readme_contains_plan_name(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "README.md").read_text()
        assert "Todo Manager" in content

    def test_config_json_is_valid_json(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "config.json").read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_raises_file_exists_error_on_non_empty_dir(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        out.mkdir()
        (out / "existing.txt").write_text("existing")
        with pytest.raises(FileExistsError):
            write_server(plan, "s", "t", out)

    def test_force_overwrites_non_empty_dir(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        out.mkdir()
        (out / "existing.txt").write_text("existing")
        write_server(plan, "new server code", "new test code", out, force=True)
        assert "new server code" in (out / "server.py").read_text()

    def test_external_packages_in_pyproject(self, tmp_path):
        plan = _sample_plan(external_packages=["httpx", "pydantic"])
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "pyproject.toml").read_text()
        assert "httpx" in content
        assert "pydantic" in content

    def test_env_vars_in_readme(self, tmp_path):
        plan = _sample_plan(env_vars=["API_KEY", "DATABASE_URL"])
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        content = (out / "README.md").read_text()
        assert "API_KEY" in content

    def test_creates_nested_output_dir(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "nested" / "deep" / "output"
        write_server(plan, "s", "t", out)
        assert out.exists()
        assert (out / "server.py").exists()

    def test_returns_resolved_path(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        returned = write_server(plan, "s", "t", out)
        assert returned == out.resolve()


class TestPathTraversal:
    """Tests for _validate_rel_path and path traversal prevention in write_server_multi."""

    def test_rejects_dotdot_path(self, tmp_path):
        with pytest.raises(ValueError, match="directory traversal"):
            _validate_rel_path("../../etc/passwd", tmp_path)

    def test_rejects_absolute_path(self, tmp_path):
        with pytest.raises(ValueError, match="absolute"):
            _validate_rel_path("/tmp/evil.py", tmp_path)

    def test_rejects_null_byte(self, tmp_path):
        with pytest.raises(ValueError, match="null byte"):
            _validate_rel_path("server\x00.py", tmp_path)

    def test_rejects_hidden_directory(self, tmp_path):
        with pytest.raises(ValueError, match="hidden"):
            _validate_rel_path(".ssh/authorized_keys", tmp_path)

    def test_rejects_dotfile(self, tmp_path):
        with pytest.raises(ValueError, match="hidden"):
            _validate_rel_path(".bashrc", tmp_path)

    def test_allows_nested_relative(self, tmp_path):
        dest = _validate_rel_path("tools/crud.py", tmp_path)
        assert dest.is_relative_to(tmp_path.resolve())

    def test_allows_simple_filename(self, tmp_path):
        dest = _validate_rel_path("server.py", tmp_path)
        assert dest.name == "server.py"

    def test_write_server_multi_rejects_traversal(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        files = {"../../evil.py": "malicious code"}
        with pytest.raises(ValueError, match="directory traversal"):
            write_server_multi(plan, files, "test code", out)

    def test_write_server_multi_allows_safe_paths(self, tmp_path):
        plan = _sample_plan()
        out = tmp_path / "output"
        files = {"server.py": "# server", "tools/utils.py": "# utils"}
        write_server_multi(plan, files, "test code", out)
        assert (out / "server.py").exists()
        assert (out / "tools" / "utils.py").exists()


class TestTemplateInjection:
    """Tests for Jinja2 template injection prevention."""

    def test_rejects_jinja_syntax_in_plan_name(self, tmp_path):
        plan = _sample_plan(name='{{ 7*7 }}')
        out = tmp_path / "output"
        with pytest.raises(ValueError, match="Jinja2 template syntax"):
            write_server(plan, "s", "t", out)

    def test_rejects_jinja_block_in_description(self, tmp_path):
        plan = _sample_plan(description='{% import os %}')
        out = tmp_path / "output"
        with pytest.raises(ValueError, match="Jinja2 template syntax"):
            write_server(plan, "s", "t", out)

    def test_allows_normal_plan_fields(self, tmp_path):
        plan = _sample_plan(name="Todo Manager", description="A todo server")
        out = tmp_path / "output"
        write_server(plan, "s", "t", out)
        assert (out / "server.py").exists()
