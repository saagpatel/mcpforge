# mcpforge — Implementation Roadmap

## Architecture

### System Overview
```
User Input (natural language description)
    ↓
[CLI (click)] → Parse flags, validate input
    ↓
[Planner] → Anthropic API call #1: Extract structured ServerPlan from description
    ↓
[Confirmation] → Display tool/resource list, get user approval (--yes skips)
    ↓
[Generator] → Anthropic API call #2: Generate server.py from ServerPlan
    ↓
[Test Generator] → Anthropic API call #3: Generate test_server.py from plan + code
    ↓
[Validator] → AST parse → ruff lint → import check → pytest run
    ↓
[Self-Heal] → If validation fails: feed errors to LLM, retry once
    ↓
[Writer] → Scaffold output directory with all files
    ↓
Output: Ready-to-run MCP server directory
```

### File Structure
```
mcpforge/
├── src/
│   └── mcpforge/
│       ├── __init__.py              # Package init, __version__
│       ├── cli.py                   # Click CLI entrypoint (generate, validate commands)
│       ├── planner.py               # LLM call #1: description → ServerPlan
│       ├── generator.py             # LLM call #2: ServerPlan → server.py source
│       ├── test_generator.py        # LLM call #3: plan + code → test_server.py source
│       ├── validator.py             # AST parse, ruff, import check, pytest run
│       ├── self_heal.py             # Error → LLM fix → revalidate (1 retry max)
│       ├── writer.py                # File output + directory scaffolding
│       ├── api_client.py            # Anthropic API wrapper with retry logic
│       ├── prompts/
│       │   ├── planner.md           # System prompt: extract tool/resource list
│       │   ├── generator.md         # System prompt: generate FastMCP server code
│       │   └── test_gen.md          # System prompt: generate pytest test suite
│       └── templates/
│           ├── pyproject.toml.j2    # Jinja2 template for generated project's pyproject.toml
│           ├── README.md.j2         # Jinja2 template for generated project's README
│           └── config.json.j2       # Claude Desktop config snippet template
├── tests/
│   ├── __init__.py
│   ├── test_models.py               # Pydantic model serialization/deserialization
│   ├── test_planner.py              # Plan extraction tests (mocked + real API)
│   ├── test_generator.py            # Code generation tests
│   ├── test_validator.py            # Validation pipeline tests with fixtures
│   ├── test_cli.py                  # CLI integration tests via click.testing
│   └── fixtures/
│       ├── sample_descriptions.py   # 10+ diverse test input descriptions
│       └── sample_plans.py          # Expected ServerPlan outputs for fixtures
├── examples/                        # 5 pre-generated example servers
│   ├── todo-server/
│   ├── weather-server/
│   ├── file-reader-server/
│   ├── database-query-server/
│   └── slack-notifier-server/
├── pyproject.toml                   # mcpforge's own project config
├── README.md
├── LICENSE                          # MIT
└── CLAUDE.md
```

### Data Model

No persistent storage. All state is in-memory during a single CLI run. Core data models:

```python
from pydantic import BaseModel, Field


class ToolParam(BaseModel):
    """A parameter for an MCP tool."""
    name: str                          # Parameter name (snake_case)
    type: str                          # Python type annotation string, e.g. "str", "int", "list[str]"
    description: str                   # Human-readable description for the tool schema
    required: bool = True
    default: str | None = None         # Default value as a string literal, or None


class ToolDef(BaseModel):
    """Definition of a single MCP tool to generate."""
    name: str                          # Function name (snake_case)
    description: str                   # Docstring — will become the tool's description in MCP
    params: list[ToolParam]            # Input parameters
    return_type: str = "dict"          # Python return type annotation
    is_async: bool = True              # Whether to generate as async def
    error_cases: list[str] = Field(    # Expected error scenarios for test generation
        default_factory=list,
        description="Human-readable error cases, e.g. 'item not found', 'invalid ID format'"
    )


class ResourceDef(BaseModel):
    """Definition of an MCP resource to generate."""
    uri_pattern: str                   # URI template, e.g. "docs://{doc_id}/content"
    name: str                          # Human-readable name
    description: str                   # Description for discovery
    is_template: bool = True           # Whether this is a URI template


class ServerPlan(BaseModel):
    """Complete structured plan for an MCP server, extracted from natural language."""
    name: str                          # Server display name, e.g. "Todo Manager"
    slug: str = ""                     # Directory/package name (auto-derived from name if empty)
    description: str                   # One-line server description
    version: str = "0.1.0"
    tools: list[ToolDef]               # Tools to generate
    resources: list[ResourceDef] = []  # Resources to generate (optional)
    env_vars: list[str] = []           # Required env vars for the generated server
    external_packages: list[str] = []  # Additional pip deps beyond fastmcp
    transport: str = "streamable-http" # Default transport protocol

    def model_post_init(self, __context) -> None:
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "-").replace("_", "-")


class ValidationResult(BaseModel):
    """Result of validating a generated MCP server."""
    syntax_ok: bool = False            # AST parse succeeded
    lint_errors: list[str] = Field(default_factory=list)
    import_ok: bool = False            # python -c "from server import mcp" succeeded
    tests_passed: bool = False         # pytest returned exit code 0
    tests_run: int = 0                 # Number of tests discovered
    tests_failed: int = 0              # Number of tests that failed
    test_output: str = ""              # Full pytest output
    errors: list[str] = Field(default_factory=list)  # All error messages

    @property
    def is_valid(self) -> bool:
        return self.syntax_ok and self.import_ok and len(self.lint_errors) == 0
```

### API Contracts

**External APIs:**

| Service | Endpoint | Method | Auth | Rate Limit | Purpose |
|---------|----------|--------|------|------------|---------|
| Anthropic Messages | `https://api.anthropic.com/v1/messages` | POST | `x-api-key` header | Tier-dependent (~4K RPM paid) | All 3 generation stages + self-heal |

**Anthropic API call patterns:**

All calls use:
- `model`: `claude-sonnet-4-20250514` (default) or user-specified via `--model`
- `max_tokens`: 8192 for planner, 16384 for generator/test_gen
- `temperature`: 0 for planner (structured extraction), 0.2 for generator/test_gen (slight creativity)
- System prompts loaded from `src/mcpforge/prompts/*.md`

**Call #1 — Planner:**
```python
# Input: user's natural language description
# System prompt: planner.md (instructs extraction of tools, resources, env vars)
# Output: JSON matching ServerPlan schema
# Parse: Pydantic validation of response
```

**Call #2 — Generator:**
```python
# Input: ServerPlan serialized as JSON
# System prompt: generator.md (instructs FastMCP 3.x code generation with patterns)
# Output: Complete server.py source code (raw text, no markdown fences)
# Parse: Extract code, AST validate
```

**Call #3 — Test Generator:**
```python
# Input: ServerPlan JSON + server.py source code
# System prompt: test_gen.md (instructs pytest test generation with FastMCP test client)
# Output: Complete test_server.py source code
# Parse: Extract code, AST validate
```

**Internal interfaces:**

```python
# api_client.py
class AnthropicClient:
    """Wrapper around anthropic.AsyncAnthropic with retry and error handling."""
    
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        ...
    
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Send a message and return the text response. Retries on rate limit (3x)."""
        ...

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        max_tokens: int = 8192,
    ) -> BaseModel:
        """Generate and parse structured JSON output into a Pydantic model."""
        ...


# planner.py
async def extract_plan(
    description: str,
    client: AnthropicClient,
    transport: str = "streamable-http",
) -> ServerPlan:
    """Parse natural language description into a structured ServerPlan."""
    ...


# generator.py
async def generate_server(
    plan: ServerPlan,
    client: AnthropicClient,
) -> str:
    """Generate complete server.py source code from a ServerPlan."""
    ...


# test_generator.py
async def generate_tests(
    plan: ServerPlan,
    server_code: str,
    client: AnthropicClient,
) -> str:
    """Generate pytest test suite for the server."""
    ...


# validator.py
async def validate_server(output_dir: Path) -> ValidationResult:
    """Run full validation pipeline: AST → ruff → import → pytest."""
    ...

def check_syntax(code: str) -> tuple[bool, list[str]]:
    """AST parse the code, return (ok, errors)."""
    ...

async def check_lint(file_path: Path) -> list[str]:
    """Run ruff check on file, return lint errors."""
    ...

async def check_import(server_path: Path) -> tuple[bool, str]:
    """Try importing the server module, return (ok, error_message)."""
    ...

async def run_tests(test_path: Path) -> tuple[bool, int, int, str]:
    """Run pytest, return (passed, total, failed, output)."""
    ...


# self_heal.py
async def attempt_fix(
    code: str,
    errors: list[str],
    client: AnthropicClient,
) -> str | None:
    """Feed errors back to LLM for one fix attempt. Returns fixed code or None."""
    ...


# writer.py
def write_server(
    plan: ServerPlan,
    server_code: str,
    test_code: str,
    output_dir: Path,
) -> Path:
    """Write all files to output directory. Returns the output path."""
    ...
```

### Dependencies

```bash
# Initialize project
uv init mcpforge --package
cd mcpforge

# Runtime dependencies
uv add anthropic click pydantic jinja2 rich

# Dev dependencies
uv add --dev pytest pytest-asyncio ruff

# Generated servers will need (installed in their own venvs):
# uv add fastmcp
```

---

## Scope Boundaries

**In scope:**
- CLI with `generate` and `validate` subcommands
- 3-stage LLM generation pipeline (plan → code → tests)
- AST + lint + import + pytest validation
- 1-retry self-heal loop
- Rich terminal UI with progress indicators
- Output: server.py, test_server.py, pyproject.toml, README.md, config.json
- 5 pre-built example servers
- --dry-run, --yes, --model, --output, --transport flags
- PyPI-publishable package

**Out of scope:**
- Web UI or hosted service
- OpenAPI spec ingestion (use Stainless/Speakeasy for that)
- Multi-file server generation (single server.py for v1)
- Custom transport implementations
- OAuth flow generation for generated servers
- IDE integrations
- Streaming output during generation

**Deferred:**
- `--template` flag with pre-built server scaffolds (Phase 2 if time permits, otherwise v1.1)
- `mcpforge update` command to add tools to existing servers (v1.1)
- Interactive mode with follow-up questions (v1.1)
- Server composition (combining multiple generated servers) (v2)
- TypeScript server generation (v2)

---

## Security & Credentials

- **Anthropic API key:** Read from `ANTHROPIC_API_KEY` env var (standard Anthropic convention). If not set, show clear error with setup instructions.
- **Data boundaries:** User's description text is sent to Anthropic API. Generated code stays 100% local. No telemetry, no analytics, no phone-home.
- **Generated server security:** All generated servers use env vars for any API keys. Never hardcode credentials. Generated README includes security notes.
- **No secrets in source:** mcpforge itself stores no secrets. No config files with keys.
- **Input handling:** User descriptions are passed as user messages to the Anthropic API. The structured plan (not raw user input) drives code generation, preventing prompt injection from description → generated code.

---

## Phase 0: Foundation (Week 1, Days 1-2)

**Objective:** Scaffolded project with working CLI skeleton, all Pydantic models defined, Anthropic API connectivity proven, and prompt template infrastructure ready.

**Tasks:**

1. Initialize uv project with src layout, pyproject.toml with proper metadata and entry point `[project.scripts] mcpforge = "mcpforge.cli:cli"` — **Acceptance:** `uv run mcpforge --help` shows usage info with generate and validate subcommands

2. Define all Pydantic models in `src/mcpforge/__init__.py` (ToolParam, ToolDef, ResourceDef, ServerPlan, ValidationResult) — **Acceptance:** `pytest tests/test_models.py` passes with tests covering:
   - ServerPlan serialization → JSON → deserialization roundtrip
   - slug auto-derivation from name
   - ValidationResult.is_valid property logic
   - ToolDef with default values

3. Implement Click CLI skeleton in `src/mcpforge/cli.py`:
   - `mcpforge generate <description>` with flags: `--output`, `--model`, `--transport`, `--yes`, `--dry-run`
   - `mcpforge validate <directory>`
   - `mcpforge version`
   — **Acceptance:** All commands parse correctly, show "Not implemented" messages gracefully

4. Implement `src/mcpforge/api_client.py` — AnthropicClient wrapper:
   - Async client initialization from env var
   - `generate()` method with retry on rate limit (3 attempts, exponential backoff)
   - `generate_json()` method with Pydantic parsing
   - Clear error on missing API key
   — **Acceptance:** Unit test with mocked httpx passes. Integration test (gated behind `ANTHROPIC_API_KEY`) sends real request and gets response.

5. Create prompt template infrastructure:
   - `src/mcpforge/prompts/planner.md` — system prompt for plan extraction (initial version)
   - `src/mcpforge/prompts/generator.md` — system prompt for code generation (initial version)
   - `src/mcpforge/prompts/test_gen.md` — system prompt for test generation (initial version)
   - Prompt loading utility that reads .md files from package
   — **Acceptance:** `from mcpforge.prompts import load_prompt; load_prompt("planner")` returns prompt string

6. Create Jinja2 output templates:
   - `templates/pyproject.toml.j2` — includes fastmcp dependency, server entry point
   - `templates/README.md.j2` — includes server name, description, setup, usage
   - `templates/config.json.j2` — Claude Desktop config snippet
   — **Acceptance:** Templates render with a sample ServerPlan, producing valid TOML/MD/JSON

**Verification checklist:**
- [ ] `uv run mcpforge --help` → shows "generate", "validate", "version" commands
- [ ] `uv run mcpforge generate --help` → shows --output, --model, --transport, --yes, --dry-run flags
- [ ] `uv run mcpforge version` → prints version number
- [ ] `pytest tests/test_models.py -v` → all model tests pass
- [ ] `pytest tests/test_cli.py -v` → CLI invocation tests pass
- [ ] `ruff check src/` → zero errors

**Risks:**
- Anthropic API key not set during development: Mock all API calls in unit tests, gate integration tests behind env var check → `pytest.mark.skipif`

---

## Phase 1: Core Generation Pipeline (Week 1, Days 3-5)

**Objective:** End-to-end generation works. `mcpforge generate "description"` produces a running FastMCP server that passes its own tests.

**Tasks:**

1. Implement `src/mcpforge/planner.py`:
   - Load planner.md system prompt
   - Send description to Anthropic API with `generate_json()` targeting ServerPlan
   - Validate extracted plan has at least 1 tool
   - Auto-derive slug from name
   — **Acceptance:** `extract_plan("A server that manages TODO items - create, list, update, delete, and search todos")` returns ServerPlan with 5 tools, each with correct params and return types

2. Refine `prompts/planner.md` system prompt:
   - Instruct model to extract tools with params, types, descriptions
   - Include FastMCP tool naming conventions (snake_case, descriptive)
   - Include 2 example input/output pairs in the prompt
   - Instruct JSON-only response matching ServerPlan schema
   — **Acceptance:** Plan extraction works correctly for 5+ diverse descriptions in test fixtures

3. Implement `src/mcpforge/generator.py`:
   - Load generator.md system prompt
   - Include FastMCP 3.x reference patterns in prompt (decorator syntax, async tools, error handling)
   - Send ServerPlan as structured context
   - Extract raw Python code from response (strip markdown fences if present)
   — **Acceptance:** Generated code for a TODO server passes AST parse and ruff check

4. Refine `prompts/generator.md` system prompt:
   - Include complete FastMCP 3.x boilerplate pattern:
     ```python
     from fastmcp import FastMCP
     mcp = FastMCP("Server Name")
     @mcp.tool
     async def tool_name(param: str) -> dict:
         """Description."""
         ...
     if __name__ == "__main__":
         mcp.run(transport="streamable-http")
     ```
   - Instruct: structured error handling with try/except, input validation, docstrings
   - Instruct: no markdown fences in output, pure Python only
   - Instruct: use env vars for any API keys/secrets
   — **Acceptance:** 3+ different generated servers all follow the same clean pattern

5. Implement `src/mcpforge/test_generator.py`:
   - Load test_gen.md system prompt
   - Send ServerPlan + generated server.py as context
   - Instruct generation of pytest tests using FastMCP's test client pattern:
     ```python
     from fastmcp import Client
     async with Client(mcp) as client:
         result = await client.call_tool("tool_name", {"param": "value"})
     ```
   - Each tool gets: 1 happy path test, 1 edge case test, 1 error case test
   — **Acceptance:** Generated tests import correctly and discover 3 × N tests (N = number of tools)

6. Implement `src/mcpforge/validator.py`:
   - `check_syntax()`: Parse code with `ast.parse()`, catch SyntaxError
   - `check_lint()`: Run `ruff check --output-format json` as subprocess, parse results
   - `check_import()`: Run `python -c "import sys; sys.path.insert(0, '.'); from server import mcp"` as subprocess
   - `run_tests()`: Run `python -m pytest test_server.py -v --tb=short` as subprocess, parse exit code and output
   - `validate_server()`: Orchestrate all checks, return ValidationResult
   — **Acceptance:** Validator correctly identifies: valid code (all checks pass), syntax errors, lint failures, import failures, test failures — tested with fixtures

7. Implement `src/mcpforge/self_heal.py`:
   - Take broken code + error messages
   - Send to LLM with prompt: "Fix this FastMCP server code. Errors: {errors}. Return only the fixed Python code."
   - Re-run validation on fixed code
   - Return fixed code if validation passes, None if still broken
   — **Acceptance:** Given a server with a known missing import, self-heal adds the import and validation passes

8. Implement `src/mcpforge/writer.py`:
   - Create output directory (error if exists, unless --force)
   - Write server.py, test_server.py from generated code
   - Render and write pyproject.toml, README.md, config.json from Jinja2 templates
   - Make server.py executable
   — **Acceptance:** Output directory contains all 5 files with correct content

9. Wire everything into CLI `generate` command in `cli.py`:
   - Parse description from argument or --file flag
   - Run planner → show plan → confirm (unless --yes) → generate → validate → self-heal if needed → write
   - Rich progress UI: spinner per stage, green/red status
   - Print summary: tools generated, validation status, output path
   - --dry-run: stop after plan display
   — **Acceptance:** Full end-to-end run produces working server

**Verification checklist:**
- [ ] `uv run mcpforge generate "A server that manages TODO items" --output /tmp/todo-server --yes` → generates complete directory in < 45 seconds
- [ ] `cd /tmp/todo-server && uv init && uv add fastmcp && uv run python server.py` → server starts on port 8000
- [ ] `cd /tmp/todo-server && uv run pytest test_server.py -v` → tests discover and ≥70% pass
- [ ] `uv run mcpforge generate "A weather lookup service that gets forecasts by city" --output /tmp/weather-server --yes` → different server, same quality
- [ ] `uv run mcpforge generate "A file reader that reads, searches, and lists files in a directory" --output /tmp/file-server --yes` → working file server
- [ ] `uv run mcpforge generate --dry-run "A database query tool"` → shows plan, no files written
- [ ] `pytest tests/ -v` → all mcpforge's own tests pass
- [ ] `ruff check src/` → zero errors

**Risks:**
- LLM generates invalid Python (20-30% of the time for complex servers): Multi-layer validation catches it → self-heal retry fixes ~50% of remaining issues → for truly broken output, write files with warning message and suggest manual fix
- LLM outputs markdown-fenced code instead of raw Python: Strip ```python and ``` before writing → regex cleanup in generator.py
- Generated tests fail because tools have mock implementations: Expected — tools with external dependencies (APIs, databases) will have stub implementations. Tests verify the tool interface, not real functionality. Document this clearly.
- FastMCP import path confusion (standalone vs SDK-bundled): Generator prompt explicitly specifies `from fastmcp import FastMCP` (standalone package). pyproject.toml template uses `fastmcp>=3.1.0` dependency.

---

## Phase 2: Polish & Distribution (Week 1, Days 6-7)

**Objective:** CLI is polished with Rich UI, package is ready for PyPI, 5 example servers demonstrate quality, validate subcommand works.

**Tasks:**

1. Enhance Rich terminal UI in cli.py:
   - Spinner with stage labels: "🔍 Planning...", "⚡ Generating server...", "🧪 Generating tests...", "✅ Validating..."
   - Color-coded validation results (green pass, red fail, yellow warning)
   - Summary panel at end: server name, tools count, validation status, output path
   - Error display with rich.traceback for API failures
   — **Acceptance:** Clean, professional CLI output with no raw print statements

2. Implement `mcpforge validate <directory>` subcommand:
   - Check directory contains server.py and test_server.py
   - Run full validation pipeline
   - Display results with Rich formatting
   — **Acceptance:** `mcpforge validate ./some-server` reports pass/fail with details

3. Generate 5 example servers and save to `examples/`:
   - `todo-server`: CRUD for TODO items with in-memory store
   - `weather-server`: Mock weather lookup by city
   - `file-reader-server`: Read, list, search files in a directory
   - `database-query-server`: SQLite query execution with safety checks
   - `slack-notifier-server`: Mock Slack message sending
   — **Acceptance:** All 5 servers start without errors and pass their test suites

4. Write comprehensive README.md for mcpforge:
   - Badges (Python version, license, PyPI)
   - One-line install: `uv pip install mcpforge`
   - Quick start with 3-line example
   - All CLI flags documented
   - 3 usage examples with sample output
   - Architecture overview
   - Contributing guide
   - Comparison table vs existing tools (Stainless, MCP-Server-Creator, etc.)
   — **Acceptance:** README covers install, usage, flags, examples, architecture

5. Add `--template` flag for pre-built starting scaffolds:
   - `rest-api`: REST API wrapper server template
   - `database`: Database query server template
   - `filesystem`: File system operations template
   - Templates provide structural hints to the generator, not full implementations
   — **Acceptance:** `mcpforge generate --template rest-api "GitHub Issues API"` generates a server with REST patterns

6. Finalize pyproject.toml for PyPI publishing:
   - Proper metadata (author, license, classifiers, URLs)
   - Entry point: `mcpforge = "mcpforge.cli:cli"`
   - Include prompts/ and templates/ as package data
   - Python ≥ 3.12 requirement
   — **Acceptance:** `uv build` produces valid wheel, `uv pip install dist/*.whl && mcpforge --help` works

7. Add LICENSE (MIT) and finalize all documentation — **Acceptance:** Repository is complete and professional

**Verification checklist:**
- [ ] `uv pip install -e .` → installs cleanly
- [ ] `mcpforge generate "A Slack message sender" --output /tmp/slack-test --yes` → clean Rich output, working server
- [ ] `mcpforge validate /tmp/slack-test` → reports validation status with colored output
- [ ] `mcpforge generate --dry-run "A database query tool"` → shows plan in rich panel, no files written
- [ ] All 5 examples in `examples/` start and pass their test suites
- [ ] `uv build` → produces .whl file
- [ ] `ruff check src/` → zero errors
- [ ] `pytest tests/ -v` → all tests pass

**Risks:**
- PyPI naming conflict: Check `mcpforge` availability on PyPI before publishing → fallback name: `mcp-forge` or `mcpserver-gen`
- Template complexity: Keep templates minimal (structural hints only, not full implementations) → they augment the LLM prompt, not replace it
