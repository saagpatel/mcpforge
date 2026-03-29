"""OpenAPI spec parser: converts OpenAPI 3.x specs to ServerPlan."""

import json
import re
from pathlib import Path

from mcpforge.models import ServerPlan, ToolDef, ToolParam

_TYPE_MAP: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list[dict]",
    "object": "dict",
}


def load_spec(path: Path) -> dict:
    """Load a JSON or YAML OpenAPI spec file."""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in (".yaml", ".yml"):
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text)  # type: ignore[no-any-return]
    return json.loads(text)  # type: ignore[no-any-return]


def _snake_case(name: str) -> str:
    """Convert a string to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_").replace(" ", "_")


def _map_type(schema_type: str) -> str:
    return _TYPE_MAP.get(schema_type, "str")


def _response_return_type(operation: dict) -> str:
    """Determine return type from operation responses."""
    try:
        schema = (
            operation["responses"]["200"]["content"]["application/json"]["schema"]
        )
        t = schema.get("type", "dict")
        if t == "array":
            return "list[dict]"
        return "dict"
    except (KeyError, TypeError):
        return "dict"


def parse_openapi(spec: dict) -> ServerPlan:
    """Convert an OpenAPI 3.x spec dict to a ServerPlan."""
    openapi_version = spec.get("openapi", "")
    if not openapi_version.startswith("3."):
        raise ValueError(
            f"Only OpenAPI 3.x is supported, got: {openapi_version!r}"
        )

    paths = spec.get("paths", {})
    if not paths:
        raise ValueError("OpenAPI spec has no paths defined")

    info = spec.get("info", {})
    name: str = info.get("title", "Generated Server")
    description: str = info.get("description", name)

    tools: list[ToolDef] = []

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue

            # Tool name from operationId or fallback
            op_id = operation.get("operationId")
            if op_id:
                tool_name = _snake_case(op_id)
            else:
                clean = path_str.replace("/", "_").strip("_")
                tool_name = f"{method.lower()}_{clean}"

            tool_description: str = operation.get("summary") or operation.get("description", "")

            # Parameters
            params: list[ToolParam] = []
            for param in operation.get("parameters", []):
                param_name: str = param.get("name", "param")
                schema_type: str = param.get("schema", {}).get("type", "string")
                py_type = _map_type(schema_type)
                param_desc: str = param.get("description", "")
                required: bool = param.get("required", param.get("in") == "path")
                params.append(ToolParam(
                    name=param_name,
                    type=py_type,
                    description=param_desc,
                    required=required,
                ))

            # requestBody → body param
            if "requestBody" in operation:
                params.append(ToolParam(
                    name="body",
                    type="dict",
                    description="Request body",
                    required=True,
                ))

            return_type = _response_return_type(operation)

            tools.append(ToolDef(
                name=tool_name,
                description=tool_description,
                params=params,
                return_type=return_type,
            ))

    if not tools:
        raise ValueError("OpenAPI spec has no operations")

    # env_vars: BASE_URL from servers, API keys from security schemes
    env_vars: list[str] = []

    servers = spec.get("servers", [])
    if servers and servers[0].get("url"):
        env_vars.append("BASE_URL")

    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    for scheme_name, scheme in security_schemes.items():
        if not isinstance(scheme, dict):
            continue
        scheme_type = scheme.get("type", "")
        if scheme_type in ("apiKey", "http"):
            env_var = scheme.get("x-env-var") or f"{scheme_name.upper()}_API_KEY"
            if env_var not in env_vars:
                env_vars.append(env_var)

    return ServerPlan(
        name=name,
        description=description,
        tools=tools,
        env_vars=env_vars,
    )
