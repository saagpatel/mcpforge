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

As of 2026-05-10, PyPI trusted publishing is working for `fastmcp-builder`
with repository `saagpatel/mcpforge`, workflow `publish.yml`, and environment
`pypi`. The `v0.3.0` tag published successfully through GitHub Actions.

```text
https://pypi.org/manage/account/publishing/
```

The package import and console commands intentionally remain `mcpforge` and
`mcpforge-server`; only the PyPI distribution name changed.

## Manual release steps

For each release, `src/mcpforge/__init__.py` and `pyproject.toml` should report
the same version, and `pyproject.toml` should use distribution name
`fastmcp-builder`.

1. Confirm version in `src/mcpforge/__init__.py` and `pyproject.toml`
2. Commit the release-prep changes.
3. Tag: `git tag vX.Y.Z`
4. Push tag: `git push origin vX.Y.Z`
5. GitHub Actions will automatically run tests and publish to PyPI

If publishing fails with `invalid-publisher`, confirm PyPI still has the
trusted publisher above before rerunning the failed `Publish to PyPI` workflow
for the tag.

## What the publish workflow does

`publish.yml` runs on a `v*` tag in three jobs:

1. `build` (read-only): checks the tag against `pyproject.toml` and
   `__version__`, runs the tests, builds the wheel and sdist with the pinned uv,
   rebuilds both from a fresh clone and fails unless the SHA-256 digests match
   (`scripts/check_reproducible_build.py`), and writes a CycloneDX SBOM of the
   locked runtime dependencies with `uv export --format cyclonedx1.5`.
2. `attest`: signs a SLSA build provenance attestation and an SBOM attestation
   for both files with `actions/attest` (Sigstore, stored on this repository).
3. `publish` (`pypi` environment): uploads the exact bytes from `build` with
   trusted publishing; `gh-action-pypi-publish` adds PEP 740 attestations.

There is no token-based or manual upload path. Do not use `twine upload` with
an API token; if CI is unavailable, wait for it rather than publishing by hand.

## Verifying a release

```bash
# PEP 740 publish attestation on PyPI
uvx pypi-attestations verify pypi --repository https://github.com/saagpatel/mcpforge \
  pypi:fastmcp_builder-X.Y.Z-py3-none-any.whl

# GitHub build provenance and SBOM attestations (releases after this workflow)
gh attestation verify fastmcp_builder-X.Y.Z-py3-none-any.whl --repo saagpatel/mcpforge
gh attestation verify fastmcp_builder-X.Y.Z-py3-none-any.whl --repo saagpatel/mcpforge \
  --predicate-type https://cyclonedx.org/bom

# Local reproducibility check of the committed source
make repro-check
```

To reproduce an older release byte for byte, build its tag with the uv version
that built it (the `Generator:` line in the wheel's `WHEEL` file), for example
`uvx --from uv==0.11.25 uv build` for 0.3.4.

## Verifying the wheel

```bash
uv build
python -m zipfile -l dist/fastmcp_builder-*.whl | grep -E "(prompts|templates)"
```

The wheel must include files under `mcpforge/prompts/` and `mcpforge/templates/`.
