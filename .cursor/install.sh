#!/usr/bin/env bash
set -euo pipefail

# Cursor Cloud starts from a clean Ubuntu image. Keep the toolchain explicit and
# install uv into the cloud user's home only when the image does not already
# provide the required version.
readonly PYTHON_VERSION="3.12.13"
readonly UV_VERSION="0.12.12"
readonly UV_BIN_DIR="${HOME}/.local/bin"

export PATH="${UV_BIN_DIR}:${PATH}"
export UV_NO_PROGRESS=1
export UV_NO_MODIFY_PATH=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

if ! command -v uv >/dev/null 2>&1 || [[ "$(uv --version | awk '{print $2}')" != "${UV_VERSION}" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "mcpforge Cursor Cloud setup requires curl to install uv ${UV_VERSION}" >&2
    exit 1
  fi
  curl --fail --silent --show-error --location \
    "https://astral.sh/uv/${UV_VERSION}/install.sh" \
    | sh
fi

command -v uv >/dev/null 2>&1
[[ "$(uv --version | awk '{print $2}')" == "${UV_VERSION}" ]]

# All inputs below are tracked by this repository; no machine-local .env files
# or credentials are read. --locked makes dependency drift fail the Build.
uv python install "${PYTHON_VERSION}"
uv lock --check
uv sync --locked --python "${PYTHON_VERSION}"

# Keep the Build useful immediately after checkout and avoid hosted provider
# calls. Hosted generation tests remain opt-in and require Cursor Secrets.
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest tests/ -q --tb=short -p no:cacheprovider
uv build
