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
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        t = schema.get("type", "dict")
        if t == "array":
            return "list[dict]"
        return "dict"
    except (KeyError, TypeError):
        return "dict"


def _schema_summary(schema: dict) -> str:
    """Return a compact schema summary for tool descriptions."""
    if not isinstance(schema, dict):
        return ""
    schema_type = schema.get("type")
    if schema_type:
        return str(schema_type)
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    return ""


def _auth_metadata(scheme_name: str, scheme: dict) -> dict[str, str] | None:
    """Return auth metadata for a supported OpenAPI security scheme."""
    scheme_type = scheme.get("type", "")
    env_var = scheme.get("x-env-var")
    if not env_var:
        base = re.sub(r"[^A-Za-z0-9_]", "_", scheme_name.upper())
        if scheme_type == "oauth2":
            env_var = f"{base}_ACCESS_TOKEN"
        elif scheme_type == "http" and scheme.get("scheme") == "bearer":
            env_var = f"{base}_BEARER_TOKEN"
        else:
            env_var = f"{base}_API_KEY"
    env_var = re.sub(r"[^A-Za-z0-9_]", "_", str(env_var))
    if env_var and not env_var[0].isalpha() and env_var[0] != "_":
        env_var = f"_{env_var}"
    metadata = {
        "scheme": scheme_name,
        "env_var": env_var,
        "location": str(scheme.get("in", "")),
        "parameter_name": str(scheme.get("name", "")),
    }
    if scheme_type == "apiKey":
        return {**metadata, "label": "api_key"}
    if scheme_type == "http" and scheme.get("scheme") == "bearer":
        return {**metadata, "label": "bearer", "location": "header"}
    if scheme_type == "oauth2":
        return {**metadata, "label": "oauth2", "location": "header"}
    if scheme_type == "http":
        return {**metadata, "label": "http", "location": "header"}
    return None


def _iter_parameters(path_item: dict, operation: dict) -> list[dict]:
    """Return path-level parameters followed by operation-level overrides."""
    merged: dict[tuple[str, str], dict] = {}
    for param in path_item.get("parameters", []):
        if isinstance(param, dict):
            merged[(str(param.get("name", "")), str(param.get("in", "")))] = param
    for param in operation.get("parameters", []):
        if isinstance(param, dict):
            merged[(str(param.get("name", "")), str(param.get("in", "")))] = param
    return list(merged.values())


def _first_json_body(operation: dict) -> tuple[dict, str, bool] | None:
    """Return the first JSON-like request body schema, media type, and required flag."""
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content", {})
    if not isinstance(content, dict):
        return None
    for media_type, media in content.items():
        if not isinstance(media, dict):
            continue
        if media_type == "application/json" or str(media_type).endswith("+json"):
            schema = media.get("schema", {})
            return (
                schema if isinstance(schema, dict) else {},
                str(media_type),
                bool(request_body.get("required", False)),
            )
    return None


def parse_openapi(
    spec: dict,
    *,
    include_tags: set[str] | None = None,
    exclude_tags: set[str] | None = None,
    operations: set[str] | None = None,
    operation_limit: int | None = None,
) -> ServerPlan:
    """Convert an OpenAPI 3.x spec dict to a ServerPlan."""
    openapi_version = spec.get("openapi", "")
    if not openapi_version.startswith("3."):
        raise ValueError(f"Only OpenAPI 3.x is supported, got: {openapi_version!r}")

    paths = spec.get("paths", {})
    if not paths:
        raise ValueError("OpenAPI spec has no paths defined")

    info = spec.get("info", {})
    name: str = info.get("title", "Generated Server")
    description: str = info.get("description", name)

    tools: list[ToolDef] = []
    env_vars: list[str] = []
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    auth_env_by_scheme: dict[str, dict[str, str]] = {}
    for scheme_name, scheme in security_schemes.items():
        if not isinstance(scheme, dict):
            continue
        auth_info = _auth_metadata(scheme_name, scheme)
        if auth_info:
            auth_env_by_scheme[scheme_name] = auth_info
            if auth_info["env_var"] not in env_vars:
                env_vars.append(auth_info["env_var"])

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
            if operations and op_id not in operations:
                continue
            if op_id:
                tool_name = _snake_case(op_id)
            else:
                clean = path_str.replace("/", "_").strip("_")
                tool_name = f"{method.lower()}_{clean}"

            operation_tags = [str(tag) for tag in operation.get("tags", [])]
            if include_tags and not include_tags.intersection(operation_tags):
                continue
            if exclude_tags and exclude_tags.intersection(operation_tags):
                continue

            tool_description: str = operation.get("summary") or operation.get("description", "")
            if not tool_description:
                tool_description = f"{method.upper()} {path_str}"

            # Parameters
            params: list[ToolParam] = []
            for param in _iter_parameters(path_item, operation):
                param_name: str = param.get("name", "param")
                schema_type: str = param.get("schema", {}).get("type", "string")
                py_type = _map_type(schema_type)
                param_desc: str = param.get("description", "")
                required: bool = param.get("required", param.get("in") == "path")
                params.append(
                    ToolParam(
                        name=param_name,
                        type=py_type,
                        description=param_desc,
                        required=required,
                        location=str(param.get("in", "")) or None,
                    )
                )

            # requestBody → body param
            body_info = _first_json_body(operation)
            if body_info:
                body_schema, media_type, body_required = body_info
                schema_summary = _schema_summary(body_schema)
                params.append(
                    ToolParam(
                        name="body",
                        type="dict",
                        description=(
                            f"Request body matching the {schema_summary} schema"
                            if schema_summary
                            else "Request body"
                        ),
                        required=body_required,
                        location="body",
                        media_type=media_type,
                    )
                )

            return_type = _response_return_type(operation)
            security = operation.get("security", spec.get("security", []))
            auth_label: str | None = None
            auth_scheme: str | None = None
            auth_env_var: str | None = None
            auth_location: str | None = None
            auth_parameter_name: str | None = None
            if isinstance(security, list):
                for requirement in security:
                    if not isinstance(requirement, dict):
                        continue
                    for scheme_name in requirement:
                        if scheme_name in auth_env_by_scheme:
                            auth_info = auth_env_by_scheme[scheme_name]
                            auth_label = auth_info["label"]
                            auth_scheme = auth_info["scheme"]
                            auth_env_var = auth_info["env_var"]
                            auth_location = auth_info["location"] or None
                            auth_parameter_name = auth_info["parameter_name"] or None
                            break
                    if auth_label:
                        break

            tools.append(
                ToolDef(
                    name=tool_name,
                    description=tool_description,
                    params=params,
                    return_type=return_type,
                    tags=operation_tags,
                    method=method.upper(),
                    path=path_str,
                    auth=auth_label,
                    auth_scheme=auth_scheme,
                    auth_env_var=auth_env_var,
                    auth_location=auth_location,
                    auth_parameter_name=auth_parameter_name,
                    retry_safe=method.upper() in {"GET", "HEAD", "OPTIONS"},
                )
            )
            if operation_limit is not None and len(tools) >= operation_limit:
                break
        if operation_limit is not None and len(tools) >= operation_limit:
            break

    if not tools:
        raise ValueError("OpenAPI spec has no operations")

    # env_vars: BASE_URL from servers, API keys/tokens from security schemes
    servers = spec.get("servers", [])
    if servers and servers[0].get("url"):
        env_vars.insert(0, "BASE_URL")
    if "REQUEST_TIMEOUT_SECONDS" not in env_vars:
        env_vars.append("REQUEST_TIMEOUT_SECONDS")

    return ServerPlan(
        name=name,
        description=description,
        tools=tools,
        env_vars=env_vars,
        external_packages=["httpx"],
        auth="mixed" if auth_env_by_scheme else None,
        openapi_metadata={
            "source": "openapi",
            "tags": sorted({tag for tool in tools for tag in tool.tags}),
            "security_schemes": sorted(auth_env_by_scheme),
            "servers": [
                str(server.get("url"))
                for server in servers
                if isinstance(server, dict) and server.get("url")
            ],
        },
    )
