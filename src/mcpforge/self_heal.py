"""Self-heal: attempts to fix a broken server.py using LLM feedback."""

import ast
import logging
import re

from mcpforge.api_client import AnthropicClient
from mcpforge.prompts import load_prompt
from mcpforge.utils import strip_code_fences

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(r"(?<![a-zA-Z0-9])[a-zA-Z0-9+/=_-]{20,}(?![a-zA-Z0-9])")


def _redact_secrets(text: str) -> str:
    """Replace long token-like strings with [REDACTED] to prevent leaking secrets."""
    return _SECRET_PATTERN.sub("[REDACTED]", text)


_FULL_REWRITE_PROMPT = """The following FastMCP 3.x server.py has errors.
Fix ALL errors and return ONLY the corrected Python code.
No markdown fences, no explanation.

## Errors
<error_output>
{errors}
</error_output>

## Current server.py
<source_code>
{code}
</source_code>"""

_SURGICAL_PROMPT = """Fix the following broken Python function(s) from a FastMCP 3.x server.
Return ONLY the fixed function(s) — no imports, no class definitions, no explanation,
no markdown fences. Preserve function signatures exactly.

## Errors
<error_output>
{errors}
</error_output>

## Broken function(s)
<source_code>
{functions}
</source_code>"""


def _extract_error_lines(errors: list[str]) -> set[int]:
    """Extract line numbers mentioned in error strings.

    Handles formats like: 'line 42', ':42:', 'line 42,', 'SyntaxError at line 42'.
    """
    lines: set[int] = set()
    for error in errors:
        for match in re.finditer(r"(?:line\s+|:)(\d+)(?:[,:\s]|$)", error, re.IGNORECASE):
            lines.add(int(match.group(1)))
    return lines


def _find_affected_functions(
    code: str,
    error_lines: set[int],
) -> list[tuple[int, int, str]]:
    """Find functions in code that contain any of the given error line numbers.

    Returns list of (start_line, end_line, source_text) for each affected function.
    Returns empty list if AST parsing fails.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    code_lines = code.splitlines()
    results: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = node.end_lineno or node.lineno
        if any(start <= line <= end for line in error_lines):
            # Extract the function source (1-indexed lines)
            func_lines = code_lines[start - 1 : end]
            results.append((start, end, "\n".join(func_lines)))

    return results


def _splice_fixed_functions(
    original_code: str,
    affected: list[tuple[int, int, str]],
    fixed_text: str,
) -> str:
    """Replace affected function regions in original_code with fixed_text.

    fixed_text is the LLM's response containing the fixed function(s).
    Splices them back in order (highest line number first to preserve offsets).
    If the fixed text can't be cleanly parsed, returns the full fixed_text as
    a best-effort replacement.
    """
    fixed_stripped = strip_code_fences(fixed_text).strip()

    # Try to parse fixed functions and match them back
    try:
        fixed_tree = ast.parse(fixed_stripped)
        fixed_funcs = [
            n for n in ast.walk(fixed_tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        fixed_lines = fixed_stripped.splitlines()
    except SyntaxError:
        # Can't parse — can't splice, fall back
        return ""

    if not fixed_funcs:
        return ""

    code_lines = original_code.splitlines()

    # Sort affected regions by start line descending (splice from bottom up)
    sorted_affected = sorted(affected, key=lambda t: t[0], reverse=True)
    # Each fixed function corresponds to each affected function in original order
    fixed_func_sources = []
    for fn in fixed_funcs:
        start = fn.lineno
        end = fn.end_lineno or fn.lineno
        fixed_func_sources.append("\n".join(fixed_lines[start - 1 : end]))

    # Map: original affected index (in original order) -> fixed source
    original_order = sorted(range(len(affected)), key=lambda i: affected[i][0])
    fix_map: dict[int, str] = {}
    for idx, orig_idx in enumerate(original_order):
        if idx < len(fixed_func_sources):
            fix_map[orig_idx] = fixed_func_sources[idx]

    # Apply splices from bottom up
    for _sorted_idx, (start, end, _) in enumerate(sorted_affected):
        # Find original index
        orig_idx = next(
            i for i, tup in enumerate(affected) if tup[0] == start and tup[1] == end
        )
        replacement = fix_map.get(orig_idx, "")
        if replacement:
            code_lines[start - 1 : end] = replacement.splitlines()

    return "\n".join(code_lines)


async def attempt_fix(code: str, errors: list[str], client: AnthropicClient) -> str | None:
    """Attempt to fix broken server.py code using LLM.

    Tries surgical patch (fix only broken functions) when ≤3 functions are affected.
    Falls back to full rewrite when >3 functions are affected, AST fails, or splice fails.

    Returns the fixed code string, or None if the fix failed or returned empty content.
    """
    error_lines = _extract_error_lines(errors)
    affected = _find_affected_functions(code, error_lines) if error_lines else []

    # Try surgical patch when 1-3 functions are affected
    if 1 <= len(affected) <= 3:
        try:
            system_prompt = load_prompt("self_heal")
            functions_text = "\n\n".join(
                f"# Function {i + 1}\n{src}" for i, (_, _, src) in enumerate(affected)
            )
            user_message = _SURGICAL_PROMPT.format(
                errors="\n".join(f"- {_redact_secrets(e)}" for e in errors),
                functions=functions_text,
            )
            raw = await client.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=8192,
                temperature=0.0,
            )
            spliced = _splice_fixed_functions(code, affected, raw)
            if spliced and spliced.strip():
                logger.debug("Self-heal: surgical patch succeeded")
                return spliced
            logger.debug("Self-heal: surgical splice failed, falling back to full rewrite")
        except Exception:
            logger.exception("Self-heal: surgical patch LLM call failed, falling back")

    # Full rewrite fallback
    try:
        system_prompt = load_prompt("self_heal")
        user_message = _FULL_REWRITE_PROMPT.format(
            errors="\n".join(f"- {_redact_secrets(e)}" for e in errors),
            code=code,
        )
        raw = await client.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=16384,
            temperature=0.0,
        )
        fixed = strip_code_fences(raw)
        return fixed if fixed.strip() else None
    except Exception:
        logger.exception("Self-heal LLM call failed")
        return None
