"""Deterministic failure semantics for generated tools."""

from mcpforge.models import ServerPlan


def plan_declares_contracts(plan: ServerPlan) -> bool:
    """Whether any tool opts the plan into failure artifacts."""
    return any(
        tool.failure_contract is not None or tool.pagination is not None for tool in plan.tools
    )
