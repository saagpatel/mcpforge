"""Pydantic data models for mcpforge."""

from pydantic import BaseModel, Field


class ToolParam(BaseModel):
    """A parameter for an MCP tool."""

    name: str
    type: str
    description: str
    required: bool = True
    default: str | None = None


class ToolDef(BaseModel):
    """Definition of a single MCP tool to generate."""

    name: str
    description: str
    params: list[ToolParam]
    return_type: str = "dict"
    is_async: bool = True
    error_cases: list[str] = Field(default_factory=list)


class ResourceDef(BaseModel):
    """Definition of an MCP resource to generate."""

    uri_pattern: str
    name: str
    description: str
    is_template: bool = False


class ServerPlan(BaseModel):
    """Complete structured plan for an MCP server, extracted from natural language."""

    name: str
    slug: str = ""
    description: str
    version: str = "0.1.0"
    tools: list[ToolDef]
    resources: list[ResourceDef] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    external_packages: list[str] = Field(default_factory=list)
    transport: str = "streamable-http"

    def model_post_init(self, __context: object) -> None:
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "-").replace("_", "-")


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
