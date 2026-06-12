"""Pydantic data models for mcpforge."""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

KNOWN_TRANSPORTS: frozenset[str] = frozenset({"streamable-http", "stdio", "sse"})

KNOWN_PACKAGES: frozenset[str] = frozenset(
    {
        "aiohttp",
        "aiosqlite",
        "asyncpg",
        "beautifulsoup4",
        "boto3",
        "cachetools",
        "celery",
        "click",
        "cryptography",
        "elasticsearch",
        "flask",
        "gql",
        "google-cloud-storage",
        "httpx",
        "lxml",
        "markdown",
        "matplotlib",
        "motor",
        "numpy",
        "opensearch-py",
        "orjson",
        "pandas",
        "pendulum",
        "pillow",
        "plotly",
        "pymongo",
        "python-dateutil",
        "python-jose",
        "pydantic",
        "pyyaml",
        "redis",
        "requests",
        "rich",
        "scipy",
        "scikit-learn",
        "seaborn",
        "sqlparse",
        "sqlalchemy",
        "starlette",
        "tenacity",
        "toml",
        "tqdm",
        "typer",
        "ujson",
        "websockets",
    }
)


class ToolParam(BaseModel):
    """A parameter for an MCP tool."""

    name: str
    type: str
    description: str
    required: bool = True
    default: str | None = None
    location: str | None = None
    media_type: str | None = None


class ToolDef(BaseModel):
    """Definition of a single MCP tool to generate."""

    name: str
    description: str
    params: list[ToolParam]
    return_type: str = "dict"
    is_async: bool = True
    error_cases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    method: str | None = None
    path: str | None = None
    auth: str | None = None
    auth_scheme: str | None = None
    auth_env_var: str | None = None
    auth_location: str | None = None
    auth_parameter_name: str | None = None
    retry_safe: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                f"Tool name {v!r} must be lowercase snake_case (e.g. 'get_user', 'list_items')"
            )
        return v

    @model_validator(mode="after")
    def validate_method_path_pair(self) -> "ToolDef":
        if (self.method is None) != (self.path is None):
            raise ValueError("'method' and 'path' must both be set or both be None")
        return self


class ResourceDef(BaseModel):
    """Definition of an MCP resource to generate."""

    uri_pattern: str
    name: str
    description: str
    is_template: bool = False
    return_type: str = "str"
    tags: list[str] = Field(default_factory=list)

    @field_validator("uri_pattern", mode="before")
    @classmethod
    def validate_uri_pattern(cls, v: str) -> str:
        """Ensure URI pattern has a valid scheme (e.g. 'file://', 'docs://')."""
        if not re.match(r"^[a-z][a-z0-9+.-]*://", v):
            raise ValueError(
                f"Invalid URI pattern: {v!r} — must start with a scheme like 'file://' or 'docs://'"
            )
        return v


class PromptDef(BaseModel):
    """Definition of an MCP prompt to generate."""

    name: str
    description: str
    params: list[ToolParam] = Field(default_factory=list)
    template: str = ""
    tags: list[str] = Field(default_factory=list)


class ServerPlan(BaseModel):
    """Complete structured plan for an MCP server, extracted from natural language."""

    name: str
    slug: str = ""
    description: str
    version: str = "0.1.0"
    tools: list[ToolDef]
    resources: list[ResourceDef] = Field(default_factory=list)
    prompts: list[PromptDef] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    external_packages: list[str] = Field(default_factory=list)
    transport: str = "streamable-http"
    auth: str | None = None
    auth_profile: str | None = None
    middleware_profiles: list[str] = Field(default_factory=list)
    openapi_metadata: dict[str, str | list[str]] = Field(default_factory=dict)

    @field_validator("transport", mode="before")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        if v not in KNOWN_TRANSPORTS:
            raise ValueError(f"Unknown transport {v!r}; expected one of {sorted(KNOWN_TRANSPORTS)}")
        return v

    @field_validator("external_packages", mode="before")
    @classmethod
    def validate_external_packages(cls, v: list[str]) -> list[str]:
        """Reject package names that could inject content into pyproject.toml."""
        _pkg_re = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
        for pkg in v:
            if not _pkg_re.match(pkg):
                raise ValueError(f"Invalid package name: {pkg!r}")
        return v

    @field_validator("env_vars", mode="before")
    @classmethod
    def validate_env_vars(cls, v: list[str]) -> list[str]:
        """Reject env var names that aren't valid shell identifiers."""
        _var_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for var in v:
            if not _var_re.match(var):
                raise ValueError(f"Invalid env var name: {var!r}")
        return v

    @classmethod
    def check_unknown_packages(cls, packages: list[str]) -> list[str]:
        """Return package names not in the known-safe set."""
        return [p for p in packages if p.lower() not in KNOWN_PACKAGES]

    def model_post_init(self, __context: object) -> None:
        if not self.slug:
            raw = self.name.lower().replace(" ", "-").replace("_", "-")
            # Strip any character that isn't alphanumeric or a hyphen (prevents path traversal)
            slug = re.sub(r"[^a-z0-9-]", "", raw)
            # Collapse multiple hyphens and strip leading/trailing hyphens
            slug = re.sub(r"-+", "-", slug).strip("-")
            self.slug = slug or "server"


class ValidationResult(BaseModel):
    """Result of validating a generated MCP server."""

    syntax_ok: bool = False
    lint_errors: list[str] = Field(default_factory=list)
    import_ok: bool = False
    tests_passed: bool = False
    tests_run: int = 0
    tests_failed: int = 0
    test_output: str = ""
    errors: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when the server is structurally sound (syntax + imports + lint).

        Deliberately excludes tests_passed: generated servers that call external
        APIs will have failing tests without credentials, but are still valid code.
        """
        return self.syntax_ok and self.import_ok and len(self.lint_errors) == 0

    @property
    def tests_ok(self) -> bool:
        """True when tests passed, were skipped, or produced no executable output."""
        return self.tests_passed or (self.tests_run == 0 and not self.test_output)
