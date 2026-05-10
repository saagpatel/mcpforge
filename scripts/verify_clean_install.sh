#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cd "$ROOT"
uv build --out-dir "$TMPDIR/dist" --clear

python3 -m venv "$TMPDIR/venv"
"$TMPDIR/venv/bin/python" -m pip install --upgrade pip >/dev/null
wheel="$(find "$TMPDIR/dist" -maxdepth 1 -name '*.whl' | sort | tail -n 1)"
"$TMPDIR/venv/bin/python" -m pip install "$wheel" >/dev/null

"$TMPDIR/venv/bin/mcpforge" version
"$TMPDIR/venv/bin/mcpforge" list examples --recursive --json >/dev/null
"$TMPDIR/venv/bin/mcpforge" doctor --json >/dev/null
