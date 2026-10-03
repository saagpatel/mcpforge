"""Untrusted default paths must not redirect generation outside the selected root."""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from mcpforge.cli import cli
from mcpforge.models import ServerPlan, ValidationResult
from mcpforge.writer import resolve_default_output_dir


def make_plan() -> ServerPlan:
    return ServerPlan(name="Safe Server", slug="safe-server", description="Control", tools=[])


@pytest.mark.parametrize(
    "slug",
    [
        "../escape",
        "/tmp/escape",
        r"..\escape",
        r"C:\escape",
        "..",
        ".hidden",
        "a/b",
        "a\\b",
        "%2e%2e%2fescape",
        "a\x00b",
        "a\nb",
        "a∕b",
    ],
)
def test_supplied_slug_rejected_at_plan_boundary(slug):
    with pytest.raises(ValidationError, match="Invalid server slug"):
        ServerPlan(name="Unsafe", slug=slug, description="Rejected", tools=[])


@pytest.mark.parametrize("slug", ["custom-slug", "Custom_Name.v2", "server123"])
def test_safe_custom_slug_preserved(slug):
    plan = ServerPlan(name="Different name", slug=slug, description="Control", tools=[])
    assert ServerPlan.model_validate_json(plan.model_dump_json()).slug == slug


@pytest.mark.parametrize("mode", ["copy", "assignment"])
def test_copied_or_mutated_slug_rejected_at_use(tmp_path, mode):
    plan = make_plan()
    if mode == "copy":
        plan = plan.model_copy(update={"slug": "../escape"})
    else:
        plan.slug = "../escape"
    with pytest.raises(ValueError, match="Invalid server slug"):
        resolve_default_output_dir(plan, tmp_path)


@pytest.mark.parametrize("target", ["outside", "root"])
def test_default_symlink_cannot_escape_or_write_root(tmp_path, target):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "safe-server").symlink_to(outside if target == "outside" else root)
    with pytest.raises(ValueError, match="outside its project root"):
        resolve_default_output_dir(make_plan(), root)
    assert not list(outside.iterdir())


def test_default_in_root_symlink_uses_canonical_project(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (tmp_path / "safe-server").symlink_to(target)
    assert resolve_default_output_dir(make_plan(), tmp_path) == target.resolve()


@pytest.mark.parametrize(
    "language,multi_file", [("python", False), ("python", True), ("typescript", False)]
)
async def test_mcp_unsafe_default_rejected_before_generation(
    tmp_path, monkeypatch, language, multi_file
):
    from mcpforge.mcp_server import generate

    monkeypatch.setenv("MCPFORGE_WORKSPACE", str(tmp_path))
    plan = make_plan().model_copy(update={"slug": "../escape"})
    with (
        patch("mcpforge.mcp_server._get_client", return_value=object()),
        patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=plan)),
        patch("mcpforge.mcp_server.generate_server", new=AsyncMock()) as python,
        patch("mcpforge.mcp_server.generate_server_multi", new=AsyncMock()) as multi,
        patch("mcpforge.mcp_server.generate_server_ts", new=AsyncMock()) as typescript,
    ):
        with pytest.raises(ValueError, match="Invalid server slug"):
            await generate("unsafe", language=language, multi_file=multi_file, no_execute=True)
    python.assert_not_called()
    multi.assert_not_called()
    typescript.assert_not_called()


@pytest.mark.parametrize("surface", ["mcp", "cli"])
@pytest.mark.parametrize("swap", ["child", "root", "ancestor"])
@pytest.mark.parametrize(
    "language,multi_file", [("python", False), ("python", True), ("typescript", False)]
)
def test_symlink_added_during_generation_cannot_redirect_write(
    tmp_path, monkeypatch, surface, swap, language, multi_file
):
    import asyncio

    envelope = tmp_path / "envelope"
    envelope.mkdir()
    root = envelope / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("MCPFORGE_WORKSPACE", str(root))

    async def generate_code(*args, **kwargs):
        if swap == "child":
            (root / "safe-server").symlink_to(outside)
        elif swap == "root":
            root.rename(tmp_path / "old-workspace")
            root.symlink_to(outside)
        else:
            envelope.rename(tmp_path / "old-envelope")
            envelope.symlink_to(outside)
            (outside / "workspace").mkdir()
        return {"server.py": "code"} if multi_file else "code"

    generator = (
        "generate_server_ts"
        if language == "typescript"
        else ("generate_server_multi" if multi_file else "generate_server")
    )
    test_generator = "generate_tests_ts" if language == "typescript" else "generate_tests"
    module = f"mcpforge.{surface if surface == 'cli' else 'mcp_server'}"
    client_factory = "_get_client" if surface == "mcp" else "_create_cli_client"
    with (
        patch(f"{module}.{client_factory}", return_value=object()),
        patch(f"{module}.extract_plan", new=AsyncMock(return_value=make_plan())),
        patch(f"{module}.{generator}", new=AsyncMock(side_effect=generate_code)),
        patch(f"{module}.{test_generator}", new=AsyncMock(return_value="tests")),
        patch(f"{module}.uv_sync", new=AsyncMock()) as sync,
        patch(f"{module}.validate_server", new=AsyncMock()) as validate,
        patch(f"{module}.validate_server_ts", new=AsyncMock()) as validate_ts,
    ):
        if surface == "mcp":
            from mcpforge.mcp_server import generate

            with pytest.raises(ValueError, match="outside its project root"):
                asyncio.run(
                    generate("control", language=language, multi_file=multi_file, no_execute=True)
                )
        else:
            args = ["generate", "control", "--yes", "--no-execute", "--language", language]
            if multi_file:
                args.append("--multi-file")
            result = CliRunner().invoke(cli, args)
            assert result.exit_code != 0
            assert "outside its project root" in " ".join(result.output.split())
    sync.assert_not_called()
    validate.assert_not_called()
    validate_ts.assert_not_called()
    assert not any(path.is_file() for path in outside.rglob("*"))


def test_update_existing_directory_with_spaces_keeps_display_working(tmp_path):
    output = tmp_path / "My Server"
    output.mkdir()
    (output / "server.py").write_text("old code")
    with (
        patch("mcpforge.cli._create_cli_client", return_value=object()),
        patch("mcpforge.cli.update_server", new=AsyncMock(return_value=("code", "tests"))),
        patch("mcpforge.cli.uv_sync", new=AsyncMock()),
        patch(
            "mcpforge.cli.validate_server",
            new=AsyncMock(return_value=ValidationResult(syntax_ok=True, import_ok=True)),
        ),
    ):
        result = CliRunner().invoke(cli, ["update", str(output), "change", "--yes"])
    assert result.exit_code == 0, result.output
    assert (output / "server.py").read_text() == "code"


def test_cli_explicit_output_outside_cwd_still_writes(tmp_path, monkeypatch):
    root = tmp_path / "cwd"
    root.mkdir()
    output = tmp_path / "selected" / "project"
    monkeypatch.chdir(root)
    with (
        patch("mcpforge.cli._create_cli_client", return_value=object()),
        patch("mcpforge.cli.extract_plan", new=AsyncMock(return_value=make_plan())),
        patch("mcpforge.cli.generate_server", new=AsyncMock(return_value="code")),
        patch("mcpforge.cli.generate_tests", new=AsyncMock(return_value="tests")),
        patch("mcpforge.cli.validate_server", new=AsyncMock(return_value=ValidationResult())),
    ):
        result = CliRunner().invoke(
            cli, ["generate", "control", "--yes", "--no-execute", "--output", str(output)]
        )
    assert result.exit_code == 0, result.output
    assert (output / "server.py").read_text() == "code"
    assert not list(root.iterdir())


async def test_mcp_default_uses_workspace_not_cwd(tmp_path, monkeypatch):
    from mcpforge.mcp_server import generate

    root = tmp_path / "workspace"
    root.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("MCPFORGE_WORKSPACE", str(root))
    with (
        patch("mcpforge.mcp_server._get_client", return_value=object()),
        patch("mcpforge.mcp_server.extract_plan", new=AsyncMock(return_value=make_plan())),
        patch("mcpforge.mcp_server.generate_server", new=AsyncMock(return_value="code")),
        patch("mcpforge.mcp_server.generate_tests", new=AsyncMock(return_value="tests")),
        patch(
            "mcpforge.mcp_server.validate_server", new=AsyncMock(return_value=ValidationResult())
        ),
    ):
        result = await generate("control", no_execute=True)
    assert result["path"] == str((root / "safe-server").resolve())
    assert (root / "safe-server" / "server.py").read_text() == "code"
    assert not list(cwd.iterdir())
