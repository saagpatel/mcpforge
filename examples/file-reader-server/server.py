"""Local filesystem reader MCP server."""

import glob
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import McpError

mcp = FastMCP("File Reader")


def _safe_path(path: str) -> Path:
    """Resolve path safely within FILES_ROOT, preventing path traversal."""
    files_root = Path(os.environ.get("FILES_ROOT", ".")).resolve()
    resolved = (files_root / path).resolve()
    if not str(resolved).startswith(str(files_root)):
        raise McpError("Access denied: path is outside FILES_ROOT")
    return resolved


@mcp.tool
async def read_file(path: str) -> dict:
    """Read a file's contents."""
    p = _safe_path(path)
    if not p.exists():
        raise McpError(f"File not found: {path!r}")
    if not p.is_file():
        raise McpError(f"Not a file: {path!r}")
    return {"path": str(p), "content": p.read_text(encoding="utf-8")}


@mcp.tool
async def list_files(directory: str = ".") -> dict:
    """List files and subdirectories in a directory."""
    d = _safe_path(directory)
    if not d.exists():
        raise McpError(f"Directory not found: {directory!r}")
    if not d.is_dir():
        raise McpError(f"Not a directory: {directory!r}")
    files = sorted(str(f.name) for f in d.iterdir() if f.is_file())
    subdirs = sorted(str(s.name) for s in d.iterdir() if s.is_dir())
    return {"directory": str(d), "files": files, "subdirectories": subdirs}


@mcp.tool
async def search_files(pattern: str) -> dict:
    """Search for files matching a glob pattern within FILES_ROOT."""
    files_root = os.environ.get("FILES_ROOT", ".")
    matches = glob.glob(pattern, root_dir=files_root, recursive=True)
    return {"pattern": pattern, "matches": sorted(matches)}


@mcp.tool
async def get_file_info(path: str) -> dict:
    """Get metadata about a file or directory."""
    p = _safe_path(path)
    if not p.exists():
        raise McpError(f"Path not found: {path!r}")
    stat = p.stat()
    return {
        "path": str(p),
        "name": p.name,
        "is_file": p.is_file(),
        "is_directory": p.is_dir(),
        "size": stat.st_size,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
