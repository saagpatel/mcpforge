"""Discovery: scan filesystem for mcpforge-generated server directories."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServerInfo:
    path: Path
    name: str        # first key in mcpServers dict from config.json
    tool_count: int  # count of @mcp.tool in server.py (or server.tool( in server.ts)
    has_tests: bool
    language: str    # "python" or "typescript"


def find_servers(root: Path, recursive: bool = False) -> list[ServerInfo]:
    """Return ServerInfo for each mcpforge server directory under root.

    A directory qualifies if it contains config.json with a 'mcpServers' key
    AND either server.py (Python) or src/server.ts (TypeScript).
    """
    pattern = "**/config.json" if recursive else "*/config.json"
    # Also check root itself
    candidates = list(root.glob(pattern))
    root_cfg = root / "config.json"
    if root_cfg.exists() and root_cfg not in candidates:
        candidates.append(root_cfg)

    results: list[ServerInfo] = []
    for cfg_path in candidates:
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if "mcpServers" not in data:
                continue
            dir_path = cfg_path.parent
            server_py = dir_path / "server.py"
            server_ts = dir_path / "src" / "server.ts"
            if server_py.exists():
                lang = "python"
                text = server_py.read_text(encoding="utf-8")
                tool_count = len(re.findall(r"@mcp\.tool", text))
                has_tests = (dir_path / "test_server.py").exists()
            elif server_ts.exists():
                lang = "typescript"
                text = server_ts.read_text(encoding="utf-8")
                tool_count = len(re.findall(r"server\.tool\(", text))
                has_tests = (dir_path / "src" / "server.test.ts").exists()
            else:
                continue
            name = next(iter(data["mcpServers"].keys()), dir_path.name)
            results.append(
                ServerInfo(
                    path=dir_path,
                    name=name,
                    tool_count=tool_count,
                    has_tests=has_tests,
                    language=lang,
                )
            )
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(results, key=lambda s: s.name)
