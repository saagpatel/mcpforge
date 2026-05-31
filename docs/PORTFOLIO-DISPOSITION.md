# mcpforge (fastmcp-builder) — Portfolio Disposition

**Status:** Active (PyPI distribution) — Python MCP server generator
**already published to PyPI** as `fastmcp-builder` at **v0.3.0** on
`origin/main`, with CLI commands `mcpforge` and `mcpforge-server`,
full OSS scaffolding wave, CVE remediation cadence visible, active
provider matrix arc (OpenAI gated readiness, hosted TypeScript
generation smoke gate, authenticated OpenAPI hardening), and a
`HANDOFF.md` + `PUBLISHING.md` pair on canonical main indicating the
operator is actively driving releases. **Second member of the PyPI
distribution cluster** that MCPAudit founded — confirms PyPI as a
real cluster, not a one-off. Unlike MCPAudit (Release Frozen at
v1.5.5 Production/Stable), mcpforge is mid-arc on v0.3.x with
**provider matrix blockers** as the explicit current frontier.

> Disposition uses strict `origin/main` verification.
> **Stabilizes the PyPI distribution cluster at 2 members** and
> demonstrates that PyPI cluster members can be either Release
> Frozen (MCPAudit) or Active (mcpforge) depending on arc state.

---

## Verification posture

This repo has **only `origin`** (`saagpatel/mcpforge`) — no
`legacy-origin` remote. Clean migration state. Local clone's `main`
is tracking `origin/main` correctly.

Specifically verified on `origin/main`:

- Tip: `369c80e` docs: record provider matrix blockers (active arc)
- **Provider matrix arc commits** (current frontier):
  - `369c80e` docs: record provider matrix blockers
  - `a6c051c` test(provider): add gated OpenAI full-path smokes
  - `b7f4519` feat(provider): add gated OpenAI readiness lane
  - `d510af4` docs: refresh auth smoke verification state
  - `3aa852e` test(openapi): add authenticated hosted smoke fixture
  - `fd3b5e4` feat(openapi): harden REST auth generation profiles
- **v0.3.0 release cadence**:
  - `a1d98ce` docs: record fastmcp-builder publish success
  - `72d2c01` chore(release): prepare fastmcp-builder v0.3.0
  - `1d49170` feat(v03): land builder roadmap surfaces
- **Earlier release + blocker history**:
  - `bb2d637` docs: prepare mcpforge 0.2.0 release
  - `9226822` docs: record PyPI login blocker
  - `be530f7` docs: record mcpforge publish blocker
- **Security hardening cadence**:
  - `e9e378b` chore(deps): fix 4 CVEs — fastmcp, pygments, cryptography
  - `3296e56` fix(security): validate external packages against
    allowlist before uv sync
  - `19cceff` fix(validation): make generated server checks truthful
  - `b212cff` fix(typescript): harden generated server validation
- **Distribution identity**:
  - PyPI package name: `fastmcp-builder`
  - Installed CLI commands: `mcpforge` and `mcpforge-server`
  - Install path: `uv tool install fastmcp-builder`
- **Operator-facing artifacts on canonical main**:
  - `HANDOFF.md` (cross-chat operator ledger)
  - `PUBLISHING.md` (release runbook)
  - `IMPLEMENTATION-ROADMAP.md`
  - `CHANGELOG.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
    `CONTRIBUTING.md`, `LICENSE`, full `.github/` templates
- Default branch: `main`

---

## Current state in one paragraph

mcpforge is a Python CLI (PyPI: `fastmcp-builder`) that generates MCP
servers from plain-English descriptions or existing OpenAPI specs.
Tools: `mcpforge generate`, `mcpforge inspect`, `mcpforge doctor`,
plus a `mcpforge-server` workspace entrypoint. Targets both
TypeScript and Python output. Currently mid-arc on **provider
expansion (v0.3.x → v0.4)**: OpenAI readiness lane gated behind a
smoke test, authenticated OpenAPI hardening for hosted generation,
provider matrix blockers documented on canonical main. Security
posture is hardened: 4 CVE fixes shipped, external package allowlist
validation before `uv sync`, generated server checks made truthful.
Per memory: all phases done, 290 tests. The current frontier is not
"is it ready to publish" (it's already on PyPI) but "expand provider
matrix beyond Anthropic without breaking the v0.3 contract."

For full detail see:
- `README.md` on `origin/main`
- `HANDOFF.md` (operator's own ledger)
- `PUBLISHING.md` (release runbook)
- `IMPLEMENTATION-ROADMAP.md`

---

## Why "Active (PyPI distribution)" — NOT Release Frozen

MCPAudit is Release Frozen at v1.5.5 Production/Stable. mcpforge is
**Active** because:

1. **Tip is `docs: record provider matrix blockers`** — the operator
   is explicitly documenting in-flight friction. Release Frozen rows
   don't have "provider matrix blockers" as their HEAD.
2. **OpenAI provider lane is gated, not landed** — `b7f4519` adds
   the *readiness* lane and `a6c051c` adds *gated* smokes. Not
   shipped to default-on.
3. **v0.3.0 published, v0.4 implied** — the provider expansion arc
   is the natural v0.4 cadence; the docs are tracking blockers
   against it.
4. **`HANDOFF.md` exists on canonical main** — operator-facing
   cross-chat artifact, characteristic of Active development not
   Release Frozen state.

This is **dual-classified**: Active for arc cadence + PyPI
distribution for cluster slot. The cluster slot is real (it's on
PyPI, installable), but the row is Active for review-cadence
purposes.

---

## Why PyPI cluster — NOT operator-tool / dogfood

GithubRepoAuditor (R11) sits in the operator-tool / dogfood shape
because the operator is the audience. mcpforge is **not** the
operator's own portfolio operating system — it is a general-purpose
MCP server generator built for external Python users:

- **PyPI distribution name `fastmcp-builder`** signals external
  developer audience
- **`uv tool install fastmcp-builder`** is a tool for any user
- **TypeScript output target** confirms cross-language ambition
- **OpenAI provider expansion** confirms "serve many users with many
  model providers" framing

The dogfood-adjacent concern applies (operator runs MCP servers, so
mcpforge bugs would affect operator stack), but the **audience** is
external, which is the cluster-decider.

---

## Cluster taxonomy update

The PyPI distribution cluster now has **two confirmed members**:

| Cluster | Count | Members |
|---|---|---|
| Signing (Apple desktop) | 22 | … |
| iOS App Store | 3 | Calibrate / Chromafield / Ghost Routes |
| Static-host (web) | 3 sub-shapes | PomGambler / HowMoneyMoves / Premise |
| Self-hosted service | 1 | RedditSentimentAnalyzer |
| **PyPI distribution** | **2** | MCPAudit (Release Frozen, v1.5.5) / **mcpforge / fastmcp-builder (Active, v0.3.0)** |
| Local-first pipeline | 1 | visual-album-studio |
| Operator-tool / dogfood | 1 | GithubRepoAuditor |
| Chrome MV3 extension | 1 | PageDiffBookmark |

PyPI cluster member states demonstrate the disposition lattice:
- **MCPAudit** = Release Frozen + Production/Stable + classifier-
  attested
- **mcpforge** = Active + mid-arc + blockers documented + dual-
  language target

The pattern: PyPI cluster membership is about **distribution
channel**; review cadence is about **arc state**. Don't conflate.

---

## Unblock trigger (operator)

This row is **already shipped to PyPI**. There is no "unblock to
release" because release is continuous. Operationally:

1. **Provider matrix blockers** — per
   `docs/provider-matrix-blockers.md` on canonical main. Operator
   decides the path to landing OpenAI readiness as default-on
   (likely needs OpenAI key in CI for smokes, or fixture-based
   tests).
2. **v0.4 cadence** — once provider matrix lands, the natural
   release is v0.4.0 with provider expansion as the headline.
3. **PyPI account security** — `9226822` recorded a "PyPI login
   blocker" earlier in the timeline. Verify current PyPI token
   rotation posture and 2FA. If using GitHub Actions for release,
   migrate to trusted publishers / OIDC instead of long-lived tokens.
4. **CVE watch on generated-server dependencies** — `e9e378b` shows
   the operator has done CVE remediation; this should be a recurring
   posture, not a one-time pass. `pip-audit` against the locked
   generated-server templates is the load-bearing check.
5. **Cross-language test gate** — TypeScript and Python target
   output both need smoke gates per release. `f309a15 docs: mark
   hosted generation smoke verified` is the cadence to maintain.

No operator-only release-readiness work blocks v0.3.0 — that is on
PyPI. The next milestone is v0.4 provider expansion.

---

## Portfolio operating system instructions

| Aspect | Posture |
|---|---|
| Portfolio status | `Active (PyPI distribution)` |
| Distribution channel | **PyPI** — `uv tool install fastmcp-builder` → `mcpforge` / `mcpforge-server` CLIs |
| Current version | **0.3.0** (mid-arc; v0.4 implied by provider expansion) |
| Audience | External Python users (general MCP server developers) |
| Review cadence | Daily / arc-driven — operator-active |
| Resurface conditions | (a) Provider matrix blockers resolved → v0.4 release, (b) CVE in fastmcp / cryptography / pygments / generated-server deps, (c) PyPI account compromise / token rotation, (d) generated-output template upstream breakage |
| Do **not** auto-add to operator-tool cluster | Audience is external |
| Do **not** auto-add to signing / App Store / static-host / extension clusters | PyPI distribution shape |
| **PyPI cluster: 2 members** | MCPAudit / **mcpforge** — confirms cluster as real, not one-off |
| Special concern | **Provider matrix scope creep.** Each new provider (OpenAI, Cohere, etc.) multiplies the test surface. Keep the gated-smoke pattern (`a6c051c`-style) — don't make providers default-on without smoke parity. |
| Special concern | **Generated-server validation truthfulness.** `19cceff fix(validation): make generated server checks truthful` is a category-bug class — generated code claiming to be valid when it isn't is the worst possible mcpforge failure mode. Keep the validation-truthfulness invariant. |
| Special concern | **External package allowlist before `uv sync`.** `3296e56` is a hard-won security posture — generated servers must not pull arbitrary unaudited deps. Preserve. |
| Special concern | **`HANDOFF.md` is operator-canonical.** Read it before assuming the active state. |

---

## Why this row stabilizes the PyPI distribution cluster

The PyPI cluster was founded by MCPAudit in R11 with "first member,
no second yet visible." mcpforge demonstrates:

- **A second PyPI member exists** — the cluster is not a one-off.
- **PyPI cluster members can be in either Release Frozen or Active
  state** — disposition lattice (cluster × state) is two independent
  axes, not a single state-machine.
- **Operator-facing artifacts (HANDOFF.md, PUBLISHING.md) are
  legitimate cluster-of-one signals for Active state**, not
  cluster-shape artifacts.
- **Security cadence (CVE fixes + allowlist validation + truthful-
  validation invariant) is shared across PyPI members** — this is a
  cluster-level concern.

Future Python packages in the portfolio batch here. The cluster is
now operationally trusted.

---

## Reactivation procedure (for the next code session)

1. **Re-read `HANDOFF.md` first** — operator's own ledger is
   authoritative for current arc state.
2. Verify `git branch -vv` shows `main` tracking `origin/main`.
   Already correct as of this disposition pass.
3. No stash created this pass — working tree was clean.
4. Re-read `PUBLISHING.md` for the release runbook.
5. Run `uv sync && pytest` — should still pass 290 tests per memory.
6. Check `docs/` for the current provider-matrix-blockers status.
7. Verify PyPI `fastmcp-builder` page is current and the operator's
   PyPI token / trusted-publisher posture is healthy.
8. Run `pip-audit` against generated-server template deps for any
   new advisories.
9. **Note:** local clone has several codex worktrees and stale
   branches (`chore/pin-sonnet-46-pre-opus-47`,
   `codex/main-v03-integration` behind 8, `codex/hosted-ts-smoke`,
   `codex/openai-*`, `codex/v03-*`). These are working-state
   artifacts, not canonical truth. Default to `origin/main`.

---

## Last known reference

| Field | Value |
|---|---|
| `origin/main` tip | `369c80e` docs: record provider matrix blockers |
| Last release | `72d2c01` chore(release): prepare fastmcp-builder v0.3.0 + `a1d98ce` publish success |
| Default branch | `main` |
| Build system | Python 3.12+ (uv-managed) + Click + pyproject.toml + uv.lock |
| Distribution | **PyPI** — `uv tool install fastmcp-builder` |
| Current version | **0.3.0** (active mid-arc toward v0.4) |
| Test count | 290 per memory |
| Target output | TypeScript + Python MCP servers |
| Active arc | **Provider matrix expansion** (OpenAI readiness gated; provider matrix blockers documented) |
| Security posture | 4 CVE fixes shipped + external package allowlist + truthful generated-server validation + hardened TypeScript validation + hardened REST auth |
| Operator artifact | **`HANDOFF.md` + `PUBLISHING.md` on canonical main** |
| Migration state | **No `legacy-origin` remote** — clean |
| Distinguishing feature | **Second PyPI distribution cluster member.** Confirms PyPI as a real cluster (not one-off). Demonstrates Active (mid-arc) state in the PyPI cluster, distinct from MCPAudit's Release Frozen Production/Stable. |
