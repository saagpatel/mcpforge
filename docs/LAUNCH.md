# LAUNCH — mcpforge 0.3.2

Release-engineering record for the 0.3.2 cut. Distribution: `fastmcp-builder`
(PyPI) · command: `mcpforge`. Branch: `release/0.3.2`.

## Why this release exists (forcing reason)

`origin/main`'s `pyproject.toml` `[project.authors]` still carried a personal
email address, and the published `0.3.1` exposed it on the PyPI project page.
**PyPI metadata is immutable** — the only way to correct the public page is to
publish a new release with scrubbed metadata. 0.3.2 is that release, taken as a
full pass rather than a metadata-only bump.

The scrub commit (`a431249`, "remove personal email from pyproject.toml authors")
lived only on `codex/chore/ruff-base-config`; this release brings it to `main`.

## Positioning

- Lead: **"one English sentence in → a tested, spec-free FastMCP 3.x server out."**
  The differentiator is *tested* output (generated pytest suite + validators) and
  *spec-free* input (no MCP schema/boilerplate to hand-write — the sentence is the
  spec).
- **No "first/only scaffolder" claim.** It would be false — prior art exists
  (e.g. mcp-generator). The README carries no such superlative.

## Channels — slow burn

- **HOLD Show HN this phase.** The Show HN copy is saved for later, paired with
  the harness essay.
- Outward surfaces for this phase (all drafted, each gated behind operator
  approval, sent one at a time): awesome-mcp-servers PR, FastMCP Discord post,
  registry submissions.

## What shipped in 0.3.2

1. **Email scrub** — cherry-picked `a431249` onto `release/0.3.2`;
   `[project.authors]` is now `{ name = "saagpatel" }` (no email).
2. **Version bump** — `0.3.1 → 0.3.2` in `pyproject.toml` and
   `src/mcpforge/__init__.py`.
3. **FastMCP currency** — dependency floor `fastmcp>=3.2.3 → >=3.4.2`; `uv.lock`
   re-resolved (added transitives `fastmcp-slim`, `griffelib`). Re-validated
   against 3.4.2 with **no live generation** (see Currency check below).
4. **Demo GIF** — rendered `docs/assets/run-and-test.gif` from
   `docs/assets/run-and-test.tape` (deterministic, no API key; drives the
   committed `examples/todo-server`). Sanitized (no home path, no update-nag, no
   Ctrl+C traceback). README embed uncommented. Hero + build-then-audit embeds
   remain commented (both require a live API key — not rendered this phase).
5. **README reposition** — tested/spec-free lead, BYOK note with a clearly-labeled
   estimated cost range, fixed the dangling `demo-assets.md` link, both names
   present (`pip install fastmcp-builder` → `mcpforge` command).
6. **CHANGELOG** — added `[0.3.2]` entry and compare-link footer.

## Reconciliation decisions (branch divergence)

Branched `release/0.3.2` off `origin/main`. Common ancestor with the codex ruff
branch was `6be93df` (#35).

- **Pulled:** email scrub `a431249` (cherry-picked clean).
- **Kept (already on main):** dep bump `#36`.
- **Dropped:** `87c9a9f` (test-fix) — byte-identical to `#37` already on main
  (verified by patch diff); cherry-picking it would duplicate.
- **Skipped `deef299` (ruff "extend from portfolio base"), intentionally.** It
  set `[tool.ruff] extend = "../ruff.toml"` — a sibling file at `~/Projects/`
  that does **not** exist in a CI checkout. CI runs `uv run ruff check .`, which
  would fail to resolve it (a documented trap). The shared baseline it points at
  is just `line-length=100` + `select=[E,F,I,UP]` — **identical to main's
  existing self-contained `[tool.ruff]` config**. So the commit added zero config
  value and only CI breakage. Its intent (config matches the portfolio baseline)
  is already satisfied; skipping it is the correct, CI-safe resolution.

## Currency check (zero credit — no live generation)

FastMCP 3.4.2 installed and imports clean everywhere. No generated-shape drift.

- Repo suite: **347 passed, 6 skipped** (skips are the API-key hosted smokes).
- `mcpforge validate` on all 11 examples: 8 Python examples pass fully; the 3
  `v03-*` examples (database / filesystem / rest-api) fail the validator's
  *Import* check **only** because their generated servers raise at import when
  required runtime env vars are absent (`DATABASE_PATH`, `WORKSPACE_ROOT`,
  `SUPPORT_API_BASE_URL`) — by design, not a fastmcp regression. With the env
  guards satisfied, all three import cleanly under 3.4.2.
- All 9 example `test_server.py` suites pass (225 example tests).

## Release gate (all green)

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 73 files already formatted |
| `pytest tests/` | 347 passed, 6 skipped |
| `mcpforge validate examples/todo-server` | Syntax/Lint/Import OK, 11 tests pass |
| `uv build` | `fastmcp_builder-0.3.2` wheel + sdist |
| `scripts/verify_clean_install.sh` | EXIT 0 — pip-installed wheel runs `mcpforge 0.3.2` |
| `/code-review` | docs/claims clean; release-coherence findings actioned (CHANGELOG) or deferred (post-ship recording) |

## GATE 1 — operator token required (publish)

On operator approval only:

1. PR `release/0.3.2` → `main`, merge.
2. Tag `v0.3.2`, push → GitHub Actions trusted-publisher (OIDC, no token) ships
   to PyPI.
3. **Verify** via `pip index versions fastmcp-builder` (shows 0.3.2) **and**
   `gh run view <id>` Publish step green — **not** the cache-laggy JSON endpoint.
4. Only then log `SHIPPED` to bridge-db.

## Post-GATE-1 recording pass (deferred, repo convention)

Mirroring how 0.3.1 was recorded (PR #33, *after* publish), update the
"current state" docs once 0.3.2 is verified live — **not** before, because they
assert "is published":

- `docs/CURRENT-STATE.md` — package version, GitHub release, PyPI publish lines.
- `docs/PROVIDER-MATRIX.md` — Current Gate Summary row (line ~14) and the
  verification command (`uvx --from fastmcp-builder==0.3.1 …` → `==0.3.2`).

## GATE 2 — operator token required, one at a time (outward, slow burn)

Drafted and held; sent only on explicit operator say-so, individually:

1. awesome-mcp-servers PR.
2. FastMCP Discord post.
3. Registry submissions.

## Next milestone (ask before building)

A real `--demo`/replay provider (recorded weather cassette) → a faithful
**zero-cost** hero GIF and a "try it offline before adding your key" feature.

## Hard constraints honored

- No Anthropic API spend — no live `mcpforge generate`; currency proven by
  install + import + generated-shape tests only.
- All work on `release/0.3.2`; nothing committed to `main`.
- Nothing outward-facing without an operator token (GATE 1 / GATE 2).
