---
name: mcpforge-cloud-workflow
description: Handle MCP Forge Cloud startup, credential-free checks, GitHub delivery, and continuation of a requested PR from any MCP Forge checkout.
---

# MCP Forge Cloud workflow

Use for authorized Cloud work or a requested PR follow-up in MCP Forge. Detect
the Git root with `git rev-parse --show-toplevel`; run commands from that root.
Read the nearest applicable [AGENTS.md](../../../AGENTS.md), supplied working
instructions, and any referenced prepared-environment startup guide first.

## Startup and scope

- Inspect the repository identity, local branch, HEAD, and `git status --short`.
  Preserve unrelated changes, existing branches, and tracked manifests/locks.
  Use the existing isolated Cloud checkout; no extra worktree is needed by default.
- Prepared startup permits authorized source edits and commits. Follow its cache
  variables and pinned Python argument for `uv sync --check --locked --offline`.
  Skip refresh if it passes. Only a stale local editable package permits the
  corresponding `uv sync --locked --offline` refresh, followed by a recheck.
  Investigate other mismatches; do not invent a fresh install, upgrade dependencies,
  or change locks to hide a startup problem.
- Local tools, configuration, sign-ins, and credentials do not automatically
  transfer. Do not read credentials, `.env` files, keychains, OAuth stores, browser
  profiles, or raw private logs. Preserve network, privacy, approval, and secret settings.
- Follow the current user's model preferences: GPT-6.1 Sol High for normal coding,
  coordination, and review; Medium for routine or clearly bounded work and helpers.
  Do not automatically escalate to Max, Extra High, or Ultra. Preferences do not
  configure the parent model picker, and helpers require supported native capabilities.

## Continue the requested PR

Resolve the exact repository and PR through supported GitHub tools. Read its
current open/closed/merged status, head repository/branch/commit, and base. Compare
those with local HEAD/status before editing. Continue that branch only when open
and consistent with the current authorization; do not create a duplicate PR or
blindly continue a closed/merged PR. Follow-up scope does not imply merge authority.

If local state is dirty, foreign, or behind the remote, inspect the differences
and preserve unrelated content before switching branches or reconciling history.
Use a safe fast-forward or normal merge when appropriate; never reset, discard,
overwrite, force-push, or silently stash other work. If safe reconciliation is
blocked, report why and continue independent authorized work. For a new task
without a requested PR, use a new task branch and create a PR only when authorized.
Fresh tasks and temporary VM state do not replace GitHub history.

## Credential-free verification

Disable all `MCPFORGE_RUN_HOSTED_*` opt-ins and keep provider keys absent for
verification commands, without displaying their values. Do not run hosted tests
or live provider calls unless the current task explicitly authorizes them.
Run the smallest meaningful check, then the repository baseline:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/ -q --tb=short -p no:cacheprovider
uv run mcpforge validate examples/todo-server
uv build
```

In a prepared environment, use the startup guide's `uv run --no-sync` and locked
cache variant. Record exact commands, exits, pass/skip counts, and the tested
contents. These checks do not prove hosted-provider or live MCP readiness. Do not
repeat a passing baseline after a wording-only refinement without a requirement
or unresolved issue that warrants it.

## Deliver and verify

Review the intended diff and commit only scoped files. Add a new commit when
continuing a published PR; do not amend its published history. Inspect supported
existing GitHub connector operations before using them. Use configured Git
transport when it works. If it fails, or the same blocker is already established
in this task, use the existing connector when it can safely preserve the requested
branch/history. Do not repeatedly retry an unchanged failure, inspect/copy tokens,
grant access, or change networking.

For connector delivery, read a fresh remote branch head and its tree before
writing. Build on that base tree with only intended file entries so other remote
content survives. Verify uploaded blob SHAs and the resulting tree against the
tested intended Git objects; create a commit whose parent is that current head.
Re-read the remote head immediately before a non-forced ref update. If it advances
or the update rejects, reconcile and rebuild from the new head; never overwrite
it with a stale tree. If reconciliation changes the delivered tree, rerun affected
behavior checks and the required baseline on the combined tree before updating
the branch. Verify publication matches that final tested state. Connector
commit metadata may differ from a local commit; compare content trees and record
the actual delivered SHA.

Read back the branch/head/tree and the exact PR after delivery. For continuation,
update that PR's title/body for the final scope and truthful verification. Check
applicable CI for the delivered head or PR merge commit; report pending, missing,
or failed checks accurately and investigate failures within scope. A connector
success response alone is not delivery proof. Leave the PR open unless the user
separately authorizes merging; publishing packages and deployment also require
their own authorization.
