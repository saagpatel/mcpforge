# SafeForge Forge Receipt v0

`ForgeReceiptV0` is mcpforge's producer-owned evidence contract for the
SafeForge research pipeline. It proves what mcpforge planned, wrote, and
checked before any dependency installation or generated-server execution.

It is not an MCPAudit report, trust grade, sandbox receipt, runtime-policy
decision, or publication approval.

## Deterministic fixture

The first fixture is `safeforge-echo-v1`:

- natural-language source description;
- one read-only, idempotent `echo` tool;
- `stdio` transport;
- no credential keys;
- no external packages beyond the generated FastMCP dependency;
- no filesystem, network, shell, or external-service capability.

`generate_safeforge_echo_fixture` uses the existing `ReplayClient` generation
path. It extracts the recorded plan, generates the recorded server and tests,
writes the normal mcpforge project, checks plan conformance, and runs static
validation with `skip_execution=True` and strict linting.

The fixture path does not call `uv_sync`, import the generated server, run its
tests, contact a provider, or launch an MCP process.

## Receipt contents

The receipt records:

- receipt and producer version;
- source-description digest, server ID, and transport;
- plan digest, provider/model identity, and environment-variable key names;
- exact generated-file inventory and SHA-256 tree digest;
- dependency-manifest digest, committed lock digest, and package identities;
- exact generated command, arguments, URL, and environment key names;
- ToolBOM identity, schema digests, explicit MCP annotation hints, and declared
  capability lists;
- per-tool implementation digests plus code-observed filesystem/network
  capabilities and literal egress destinations;
- syntax, static security, and lint states;
- explicit skipped import and test states;
- limitations stating that this is preinstall generation evidence only.

Receipt creation fails when generated tool code uses an undeclared literal
egress destination, performs dynamic network egress while `open_world_hint` is
false, or uses network capability without either a destination or an open-world
declaration. Observation is intentionally module-wide and follows import aliases,
so every tool binds the full server implementation digest and conservatively
inherits filesystem/network behavior found anywhere in that server module.
Observed filesystem access requires the exact `filesystem` permission.
Static security warnings are unresolved review requirements: they set security
to `failed` and make the receipt ineligible for preinstall audit.

The source description and file contents are not embedded. Artifact paths are
portable relative paths. Unexpected files or symlinks block receipt creation
before their contents are read.

## Contract files

- Pydantic model and builder: `src/mcpforge/forge_receipt.py`
- Generated schema: `examples/schemas/forge-receipt-v0.schema.json`
- Deterministic generator: `src/mcpforge/safeforge_fixture.py`
- Regression tests: `tests/test_safeforge_fixture.py`

The committed JSON Schema is generated from the live Pydantic model and tested
for exact equality. Contract v0 accepts exactly receipt version `0.1.0`; broader
compatibility belongs after MCPAudit consumes the first real receipt.

## Cross-repository acceptance replay

`scripts/verify_safeforge_handoff.py` generates the trusted replay fixture with
`static-no-execute` validation, writes its schema and receipt only to a temporary
directory, and invokes an existing MCPAudit virtual environment's public
`safeforge-preinstall` and `safeforge-run` commands twice. It requires
byte-identical preinstall results and identical final runtime manifests with all
thirteen stages, an eligible decision, zero egress, and verified cleanup. Only
the runtime command installs and executes, and it does so inside MCPAudit's
disposable boundary.

```bash
.venv/bin/python scripts/verify_safeforge_handoff.py \
  --mcpaudit-repo /path/to/MCPAudit
```
