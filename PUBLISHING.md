# Publishing mcpforge to PyPI

## Prerequisites

- PyPI project or trusted publishing setup for `mcpforge`
- GitHub Actions `pypi` environment configured for trusted publishing
- `uv` installed

## Manual release steps

For `v0.2.0`, `src/mcpforge/__init__.py` and `pyproject.toml` already report
`0.2.0`. Do not bump again unless intentionally cutting a later release.

1. Confirm version in `src/mcpforge/__init__.py` and `pyproject.toml`
2. Commit the release-prep changes.
3. Tag: `git tag vX.Y.Z`
4. Push tag: `git push origin vX.Y.Z`
5. GitHub Actions will automatically run tests and publish to PyPI

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
python -m zipfile -l dist/mcpforge-*.whl | grep -E "(prompts|templates)"
```

The wheel must include files under `mcpforge/prompts/` and `mcpforge/templates/`.
