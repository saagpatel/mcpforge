"""Tests for planner.refine_plan()."""

from unittest.mock import AsyncMock, patch

import pytest

from mcpforge.models import ServerPlan, ToolDef
from mcpforge.planner import refine_plan


def _mock_plan() -> ServerPlan:
    return ServerPlan(
        name="Todo Manager",
        slug="todo-manager",
        description="A todo server",
        tools=[ToolDef(name="create_todo", description="Create todo", params=[])],
    )


class TestRefinePlan:
    async def test_embeds_plan_json_in_user_message(self):
        """refine_plan includes the existing plan JSON in the user_message."""
        plan = _mock_plan()
        mock_client = AsyncMock()
        mock_client.generate_json = AsyncMock(return_value=_mock_plan())

        with patch("mcpforge.planner.load_prompt", return_value="system"):
            await refine_plan(plan, "add a delete tool", mock_client)

        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert "todo-manager" in call_kwargs["user_message"]  # slug from plan JSON

    async def test_embeds_feedback_in_user_message(self):
        """refine_plan includes the feedback text in the user_message."""
        plan = _mock_plan()
        mock_client = AsyncMock()
        mock_client.generate_json = AsyncMock(return_value=_mock_plan())

        with patch("mcpforge.planner.load_prompt", return_value="system"):
            await refine_plan(plan, "add a search tool", mock_client)

        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert "add a search tool" in call_kwargs["user_message"]

    async def test_raises_value_error_when_no_tools(self):
        """refine_plan raises ValueError if refined plan has no tools."""
        plan = _mock_plan()
        empty_plan = ServerPlan(
            name="Empty", description="No tools", tools=[]
        )
        mock_client = AsyncMock()
        mock_client.generate_json = AsyncMock(return_value=empty_plan)

        with patch("mcpforge.planner.load_prompt", return_value="system"):
            with pytest.raises(ValueError, match="no tools"):
                await refine_plan(plan, "remove everything", mock_client)

    async def test_returns_server_plan(self):
        """refine_plan returns the ServerPlan from generate_json."""
        plan = _mock_plan()
        refined = ServerPlan(
            name="Enhanced Todo",
            description="Enhanced server",
            tools=[
                ToolDef(name="create_todo", description="Create", params=[]),
                ToolDef(name="delete_todo", description="Delete", params=[]),
            ],
        )
        mock_client = AsyncMock()
        mock_client.generate_json = AsyncMock(return_value=refined)

        with patch("mcpforge.planner.load_prompt", return_value="system"):
            result = await refine_plan(plan, "add delete", mock_client)

        assert result.name == "Enhanced Todo"
        assert len(result.tools) == 2

    async def test_uses_planner_system_prompt(self):
        """refine_plan loads the 'planner' prompt."""
        plan = _mock_plan()
        mock_client = AsyncMock()
        mock_client.generate_json = AsyncMock(return_value=_mock_plan())

        with patch("mcpforge.planner.load_prompt", return_value="planner system") as mock_load:
            await refine_plan(plan, "feedback", mock_client)

        mock_load.assert_called_once_with("planner")
        call_kwargs = mock_client.generate_json.call_args.kwargs
        assert call_kwargs["system_prompt"] == "planner system"
