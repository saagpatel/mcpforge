# Publishing mcpforge to PyPI

## Prerequisites

- PyPI project or trusted publishing setup for `fastmcp-builder`
- GitHub Actions `pypi` environment configured for trusted publishing
- `uv` installed

## Trusted publishing setup

The publish workflow uses PyPI trusted publishing. Configure the PyPI project
publisher to match these GitHub claims:

- PyPI project: `fastmcp-builder`
- Owner: `saagpatel`
- Repository: `mcpforge`
- Workflow: `publish.yml`
- Environment: `pypi`

The first `v0.2.0` publish attempt on 2026-05-10 built and tested
successfully, then failed at the PyPI publish step with `invalid-publisher`
because PyPI had no matching trusted publisher. After account verification,
PyPI rejected the original `mcpforge` distribution name as too similar to
existing projects including `mcp-forge` and `mcp-forge-cli`.

As of 2026-05-10, PyPI has a pending trusted publisher for `fastmcp-builder`
with repository `saagpatel/mcpforge`, workflow `publish.yml`, and environment
`pypi`.

```text
https://pypi.org/manage/account/publishing/
```

The package import and console commands intentionally remain `mcpforge` and
`mcpforge-server`; only the PyPI distribution name changed.

## Manual release steps

For `v0.3.0`, `src/mcpforge/__init__.py` and `pyproject.toml` should report
`0.3.0`, and `pyproject.toml` should use distribution name
`fastmcp-builder`.

1. Confirm version in `src/mcpforge/__init__.py` and `pyproject.toml`
2. Commit the release-prep changes.
3. Tag: `git tag vX.Y.Z`
4. Push tag: `git push origin vX.Y.Z`
5. GitHub Actions will automatically run tests and publish to PyPI

If publishing fails with `invalid-publisher`, confirm PyPI still has the
pending publisher above before rerunning the failed `Publish to PyPI` workflow
for the tag.

## Manual publish (without CI)

```bash
uv build
ls dist/
pip install twine
twine upload dist/*
```

## Verifying the wheel

```bash
uv build
python -m zipfile -l dist/fastmcp_builder-*.whl | grep -E "(prompts|templates)"
```

The wheel must include files under `mcpforge/prompts/` and `mcpforge/templates/`.
