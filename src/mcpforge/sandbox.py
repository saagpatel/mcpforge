"""Sandbox: restrict execution of AI-generated code during validation.

Uses macOS sandbox-exec (seatbelt) when available, with resource limits
via setrlimit as a cross-platform fallback. Controlled by environment:
  MCPFORGE_NO_SANDBOX=1  — disable all sandboxing (for CI or non-macOS)
"""

import os
import sys
from pathlib import Path

_SANDBOX_DISABLED = os.environ.get("MCPFORGE_NO_SANDBOX", "") == "1"

# macOS seatbelt profile: deny-default, allow only what's needed.
# {output_dir} is replaced at runtime with the actual output directory.
_SEATBELT_PROFILE = """\
(version 1)
(deny default)
(allow file-read*)
(allow file-write*
    (subpath "{output_dir}")
    (subpath "/private/var/folders")
    (subpath "/var/folders")
    (subpath "/tmp")
)
(allow process-exec)
(allow process-fork)
(allow sysctl-read)
(allow mach-lookup)
(allow mach-register)
(allow signal)
(allow ipc-posix-shm-read-data)
(allow ipc-posix-shm-write-data)
(allow ipc-posix-shm-write-create)
(deny network*)
"""


def sandboxed_command(cmd: list[str], output_dir: Path) -> list[str]:
    """Wrap a command with macOS sandbox-exec if available.

    On macOS: prepends sandbox-exec with a deny-default seatbelt profile
    that blocks network access and restricts file writes to output_dir.
    On other platforms: returns the command unchanged.
    If MCPFORGE_NO_SANDBOX=1: returns the command unchanged.
    """
    if _SANDBOX_DISABLED or sys.platform != "darwin":
        return cmd

    profile = _SEATBELT_PROFILE.format(output_dir=str(output_dir.resolve()))
    return ["sandbox-exec", "-p", profile, *cmd]


def sandbox_preexec(output_dir: Path) -> "callable[[], None] | None":
    """Return a preexec_fn that sets resource limits for subprocess execution.

    Sets CPU time limit (30s) and address space limit (512MB).
    Returns None when sandboxing is disabled.
    """
    if _SANDBOX_DISABLED:
        return None

    def _set_limits() -> None:
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
            # 512 MB address space limit
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except (ValueError, OSError):
            pass  # Resource limits not available on this platform

    return _set_limits
