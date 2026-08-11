---
name: repo-onboarding
description: Onboard quickly into the mcpforge codebase. Use this skill when working in ~/Projects/mcpforge to understand the product shape, core architecture, validation flow, and safest places to change code before making edits.
effort: low
---

# repo-onboarding

<!-- beginner-glance:start -->
## Beginner At A Glance
- What this skill does: Gives a fast mental model of how `mcpforge` is laid out and where to look first.
- Use this when: Use when starting work in `mcpforge`, especially before changing generation, validation, or CLI behavior.
- Say it naturally: "Onboard me to mcpforge" | "How is mcpforge structured?" | "Where should I edit this in mcpforge?"
<!-- beginner-glance:end -->

## PM Output Style
- Use the big-picture PM update format by default: Project, Goal, Headline, State, Impact, Why it matters, What you need from me, Blockers.
- Keep language beginner-friendly and avoid technical receipts unless explicitly requested.

## Skill Contract v2

use_when:
- The current workspace is `~/Projects/mcpforge`.
- The user asks for onboarding, architecture, safe edit targets, or a quick mental model before changes.
- A request touches generation, validation, CLI behavior, MCP server output, or tests and repo context would reduce risk.

dont_use_when:
- The task is a tiny isolated edit where repo structure is already obvious from the touched file.

trigger_phrases:
- onboard me to mcpforge; explain this repo; where should I change this; how is mcpforge organized

anti_triggers:
- one-line typo only

expected_inputs:
- User goal, touched area if known, and current repo state.

expected_outputs:
- Short repo map, likely edit points, validation path, and top risks.

success_criteria:
- A collaborator can start editing the right files with a clear understanding of how to verify the change.

companion_skills:
- mcp-debugger,promptfoo-eval-loop,quality-gatekeeper

risk_class: low

default_chain_role: primary

## Repo Map

- `README.md`: product promise, CLI surface, and supported workflows.
- `pyproject.toml`: package metadata, dependencies, scripts, and test/lint defaults.
- `src/`: primary implementation. Start here for CLI, planning, generation, validation, and MCP server code.
- `tests/`: regression surface. Prefer adding or updating tests when behavior changes.
- `examples/`: useful for understanding generated output and intended use patterns.
- `HANDOFF.md` and `IMPLEMENTATION-ROADMAP.md`: good context when the task is roadmap-shaped rather than purely local.

## Working Heuristics

- Start from the user-facing command or behavior, then trace inward to the implementation under `src/`.
- Treat the pipeline as three linked surfaces: plan -> generate -> validate. Changes in one stage often affect the others.
- Keep generated output quality and validation behavior aligned. If you change generation assumptions, check whether tests, lint, or self-heal expectations also need to move.
- Preserve the repo's promise of "production-ready MCP servers from a sentence." That usually means avoiding changes that make the happy path more complex unless the gain is clear.

## First Places To Look

- CLI or flags changed: look for the CLI entrypoint and command wiring under `src/`.
- Output project shape changed: inspect generation templates or code emitters under `src/`.
- Validation or self-heal changed: inspect validation pipeline code and related tests first.
- MCP-facing behavior changed: inspect the generated server examples plus tests to verify the external contract still makes sense.

## Verification Pattern

- Run the smallest targeted test that proves the edited behavior.
- If generation output changes, run the relevant validation path too, not just unit tests.
- Prefer checking one representative end-to-end command before declaring success.
- Call out any limits clearly if the task depends on external model keys or networked APIs.
