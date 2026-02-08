"""Tests for ClaudeCodeTool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.agent.tools.claude_code import ClaudeCodeTool
from nanobot.bridge.claude_code import ClaudeCodeBridge
from nanobot.bus.queue import MessageBus


class TestToolSchema:
    """Tests for tool schema definition."""

    def test_tool_schema(self):
        bridge = MagicMock(spec=ClaudeCodeBridge)
        bus = MagicMock(spec=MessageBus)
        tool = ClaudeCodeTool(bridge=bridge, bus=bus)

        assert tool.name == "claude_code"
        assert "requirement" in tool.parameters["properties"]
        assert "working_dir" in tool.parameters["properties"]
        assert "requirement" in tool.parameters["required"]
        assert tool.description  # Non-empty description


class TestSetContext:
    """Tests for set_context."""

    def test_set_context(self):
        bridge = MagicMock(spec=ClaudeCodeBridge)
        bus = MagicMock(spec=MessageBus)
        tool = ClaudeCodeTool(bridge=bridge, bus=bus)

        # Default values
        assert tool._channel == "cli"
        assert tool._chat_id == "direct"

        # After set_context
        tool.set_context("telegram", "chat-123")
        assert tool._channel == "telegram"
        assert tool._chat_id == "chat-123"


class TestExecute:
    """Tests for execute."""

    @pytest.mark.asyncio
    async def test_execute_starts_task(self):
        bridge = MagicMock(spec=ClaudeCodeBridge)
        bridge.start_task = AsyncMock()
        bus = MagicMock(spec=MessageBus)
        tool = ClaudeCodeTool(bridge=bridge, bus=bus)

        result = await tool.execute(requirement="Build a feature")

        bridge.start_task.assert_called_once()
        call_kwargs = bridge.start_task.call_args
        assert call_kwargs.kwargs["requirement"] == "Build a feature"
        assert call_kwargs.kwargs["on_output"] is not None
        assert call_kwargs.kwargs["on_question"] is not None
        assert call_kwargs.kwargs["on_complete"] is not None
        assert "task started" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        bridge = MagicMock(spec=ClaudeCodeBridge)
        bridge.start_task = AsyncMock(side_effect=RuntimeError("Process failed"))
        bus = MagicMock(spec=MessageBus)
        tool = ClaudeCodeTool(bridge=bridge, bus=bus)

        result = await tool.execute(requirement="Broken task")

        assert "error" in result.lower()
        assert "Process failed" in result
