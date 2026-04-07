"""Tests for mcpforge sandbox module."""

import os
from pathlib import Path
from unittest.mock import patch

from mcpforge.sandbox import sandbox_preexec, sandboxed_command


class TestSandboxedCommand:
    def test_prepends_sandbox_exec_on_macos(self, tmp_path: Path):
        with (
            patch("mcpforge.sandbox._SANDBOX_DISABLED", False),
            patch("mcpforge.sandbox.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            cmd = sandboxed_command(["uv", "run", "python"], tmp_path)
            assert cmd[0] == "sandbox-exec"
            assert cmd[1] == "-p"
            assert "uv" in cmd
            assert "run" in cmd
            assert "python" in cmd

    def test_passthrough_on_linux(self, tmp_path: Path):
        with (
            patch("mcpforge.sandbox._SANDBOX_DISABLED", False),
            patch("mcpforge.sandbox.sys") as mock_sys,
        ):
            mock_sys.platform = "linux"
            cmd = sandboxed_command(["uv", "run", "python"], tmp_path)
            assert cmd == ["uv", "run", "python"]

    def test_disabled_by_env_var(self, tmp_path: Path):
        with patch("mcpforge.sandbox._SANDBOX_DISABLED", True):
            cmd = sandboxed_command(["uv", "run", "python"], tmp_path)
            assert cmd == ["uv", "run", "python"]

    def test_profile_contains_output_dir(self, tmp_path: Path):
        with (
            patch("mcpforge.sandbox._SANDBOX_DISABLED", False),
            patch("mcpforge.sandbox.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            cmd = sandboxed_command(["uv", "run"], tmp_path)
            profile = cmd[2]  # The -p argument
            assert str(tmp_path.resolve()) in profile

    def test_profile_denies_network(self, tmp_path: Path):
        with (
            patch("mcpforge.sandbox._SANDBOX_DISABLED", False),
            patch("mcpforge.sandbox.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            cmd = sandboxed_command(["uv", "run"], tmp_path)
            profile = cmd[2]
            assert "(deny network*)" in profile


class TestSandboxPreexec:
    def test_returns_callable(self, tmp_path: Path):
        with patch("mcpforge.sandbox._SANDBOX_DISABLED", False):
            fn = sandbox_preexec(tmp_path)
            assert callable(fn)

    def test_returns_none_when_disabled(self, tmp_path: Path):
        with patch("mcpforge.sandbox._SANDBOX_DISABLED", True):
            fn = sandbox_preexec(tmp_path)
            assert fn is None
