# Release draft — 0.3.1

Ready-to-apply notes for cutting **v0.3.1** (a patch release: dependency
security fixes + docs). The fixes are already on `main`; this just publishes them.

> **Lane:** version bump + tag + publish are the packaging/CI lane (Codex).
> This file is a draft handoff — delete it after the release lands.

## What 0.3.1 ships

A patch release. No API or behavior changes — transitive dependency security
upgrades (`idna`, `starlette`) plus a dev-only example fixture bump (`vitest`),
and the README/launch documentation overhaul. Safe drop-in over 0.3.0.

## Release steps

1. Bump `version` in `pyproject.toml`: `0.3.0` → `0.3.1`.
2. In `CHANGELOG.md`, replace the `## [Unreleased]` heading over the current
   entries with `## [0.3.1] - <RELEASE-DATE>`, then add a fresh empty
   `## [Unreleased]` above it (see block below). Set `<RELEASE-DATE>` to the
   actual tag date (YYYY-MM-DD).
3. Update the CHANGELOG compare-link footer (see below).
4. Commit (`chore(release): 0.3.1`), tag `v0.3.1`, push the tag.
5. The `Publish to PyPI` workflow fires on the tag → verify `fastmcp-builder`
   0.3.1 appears on PyPI and the GitHub release is created.

## CHANGELOG block (paste in place of current `[Unreleased]`)

```markdown
## [Unreleased]

No unreleased changes.

## [0.3.1] - <RELEASE-DATE>

### Security

- Upgraded `idna` (3.11 → 3.18) and `starlette` (1.0.0 → 1.2.1) in the locked
  dependency set, resolving GHSA-65pc-fj4g-8rjx (CVE-2026-45409) and
  GHSA-86qp-5c8j-p5mr (CVE-2026-48710).
- Upgraded `vitest` to `^4.1.0` in the TypeScript example fixtures, resolving
  GHSA-5xrq-8626-4rwp (CVE-2026-47429). Development-only dependency in the
  examples; not part of the published `fastmcp-builder` distribution.

### Documentation

- Rewrote the README into a 60-second quick start with PyPI, Python, and CI
  badges, a synthetic sample generated server, and copy-paste commands.
- Added a "Build, then audit" section pairing mcpforge with the companion
  `mcp-audit` (`mcp-permission-audit`) tool.
- Added reproducible vhs demo tapes under `docs/assets/` with pre-staged README
  embed slots, plus a `demo-assets.md` shot-list and `launch-posts.md` drafts.
```

## CHANGELOG compare-link footer (replace the current `[Unreleased]` line, add `[0.3.1]`)

```markdown
[Unreleased]: https://github.com/saagpatel/mcpforge/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/saagpatel/mcpforge/releases/tag/v0.3.1
```

## GitHub release notes (short blurb)

```markdown
**0.3.1 — security + docs patch**

Drop-in over 0.3.0. Patches three dependency advisories (idna, starlette, and a
dev-only vitest fixture) and overhauls the README into a 60-second quick start
with demos and the mcp-audit toolkit pairing. No API or behavior changes.

`uv tool install fastmcp-builder` / `pip install -U fastmcp-builder`
```
