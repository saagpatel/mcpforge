# Publishing mcpforge to PyPI

## Prerequisites

- PyPI project or trusted publishing setup for `mcpforge`
- GitHub Actions `pypi` environment configured for trusted publishing
- `uv` installed

## Trusted publishing setup

The publish workflow uses PyPI trusted publishing. Configure the PyPI project
publisher to match these GitHub claims:

- PyPI project: `mcpforge`
- Owner: `saagpatel`
- Repository: `mcpforge`
- Workflow: `publish.yml`
- Environment: `pypi`

The first `v0.2.0` publish attempt on 2026-05-10 built and tested
successfully, then failed at the PyPI publish step with `invalid-publisher`
because PyPI had no matching trusted publisher.

As of 2026-05-10, PyPI still returns 404 for `mcpforge`, so use PyPI's
pending-publisher flow at:

```text
https://pypi.org/manage/account/publishing/
```

PyPI requires an authenticated account session before this can be added.
The setup attempt reached the login page for that publishing URL, so the next
manual action is to log in and add the pending GitHub Actions publisher with
the values above.

## Manual release steps

For `v0.2.0`, `src/mcpforge/__init__.py` and `pyproject.toml` already report
`0.2.0`. Do not bump again unless intentionally cutting a later release.

1. Confirm version in `src/mcpforge/__init__.py` and `pyproject.toml`
2. Commit the release-prep changes.
3. Tag: `git tag vX.Y.Z`
4. Push tag: `git push origin vX.Y.Z`
5. GitHub Actions will automatically run tests and publish to PyPI

If publishing fails with `invalid-publisher`, configure the trusted publisher
above, then rerun the failed `Publish to PyPI` workflow for the existing tag.

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
