# Publishing mcpforge to PyPI

## Prerequisites

- PyPI account with token
- `uv` installed

## Manual release steps

1. Bump version in `src/mcpforge/__init__.py` and `pyproject.toml`
2. Commit: `git commit -m "chore: bump version to X.Y.Z"`
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
