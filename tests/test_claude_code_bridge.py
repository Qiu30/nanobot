"""Tests for ClaudeCodeBridge."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.bridge.claude_code import ClaudeCodeBridge, TaskStatus


class TestBuildCommand:
    """Tests for _build_command."""

    def test_build_command_default(self):
        bridge = ClaudeCodeBridge()
        cmd = bridge._build_command()
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--dangerously-skip-permissions" in cmd
        # No --allowedTools or --model when not specified
        assert "--allowedTools" not in cmd
        assert "--model" not in cmd

    def test_build_command_with_allowed_tools(self):
        bridge = ClaudeCodeBridge(allowed_tools=["Read", "Write", "Bash"])
        cmd = bridge._build_command()
        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        assert cmd[idx + 1] == "Read,Write,Bash"
        # Should NOT have --dangerously-skip-permissions when allowed_tools is set
        assert "--dangerously-skip-permissions" not in cmd

    def test_build_command_with_model(self):
        bridge = ClaudeCodeBridge(model="claude-opus-4-6")
        cmd = bridge._build_command()
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-4-6"

    def test_build_command_custom_bin(self):
        bridge = ClaudeCodeBridge(claude_bin="/usr/local/bin/claude")
        cmd = bridge._build_command()
        assert cmd[0] == "/usr/local/bin/claude"


class TestStartTask:
    """Tests for start_task."""

    @pytest.mark.asyncio
    async def test_start_task(self):
        bridge = ClaudeCodeBridge()

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b"")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=0)

        on_output = AsyncMock()
        on_question = AsyncMock()
        on_complete = AsyncMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            await bridge.start_task(
                task_id="test-1",
                requirement="Fix the bug",
                on_output=on_output,
                on_question=on_question,
                on_complete=on_complete,
            )

        assert "test-1" in bridge._tasks
        assert bridge._tasks["test-1"]["status"] == TaskStatus.RUNNING

        # Verify stdin was written with the requirement
        mock_process.stdin.write.assert_called_once()
        written_data = mock_process.stdin.write.call_args[0][0]
        parsed = json.loads(written_data.decode("utf-8").strip())
        assert parsed["type"] == "user_message"
        assert parsed["content"] == "Fix the bug"

    @pytest.mark.asyncio
    async def test_start_task_duplicate_id(self):
        bridge = ClaudeCodeBridge()

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b"")
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=0)

        on_output = AsyncMock()
        on_question = AsyncMock()
        on_complete = AsyncMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            await bridge.start_task(
                task_id="dup-1",
                requirement="Task 1",
                on_output=on_output,
                on_question=on_question,
                on_complete=on_complete,
            )
            with pytest.raises(ValueError, match="already exists"):
                await bridge.start_task(
                    task_id="dup-1",
                    requirement="Task 2",
                    on_output=on_output,
                    on_question=on_question,
                    on_complete=on_complete,
                )


class TestSendAnswer:
    """Tests for send_answer."""

    @pytest.mark.asyncio
    async def test_send_answer(self):
        bridge = ClaudeCodeBridge()

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()

        bridge._tasks["task-1"] = {
            "process": mock_process,
            "status": TaskStatus.WAITING_FOR_ANSWER,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        await bridge.send_answer("task-1", "Yes, proceed")

        assert bridge._tasks["task-1"]["status"] == TaskStatus.RUNNING
        mock_process.stdin.write.assert_called_once()
        written_data = mock_process.stdin.write.call_args[0][0]
        parsed = json.loads(written_data.decode("utf-8").strip())
        assert parsed["type"] == "user_message"
        assert parsed["content"] == "Yes, proceed"

    @pytest.mark.asyncio
    async def test_send_answer_not_waiting(self):
        bridge = ClaudeCodeBridge()

        mock_process = MagicMock()
        bridge._tasks["task-2"] = {
            "process": mock_process,
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        with pytest.raises(ValueError, match="not waiting for an answer"):
            await bridge.send_answer("task-2", "answer")

    @pytest.mark.asyncio
    async def test_send_answer_not_found(self):
        bridge = ClaudeCodeBridge()
        with pytest.raises(ValueError, match="not found"):
            await bridge.send_answer("nonexistent", "answer")


class TestCancelTask:
    """Tests for cancel_task."""

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        bridge = ClaudeCodeBridge()

        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)

        bridge._tasks["task-c"] = {
            "process": mock_process,
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        await bridge.cancel_task("task-c")

        mock_process.terminate.assert_called_once()
        assert bridge._tasks["task-c"]["status"] == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self):
        bridge = ClaudeCodeBridge()
        # Should not raise, just return
        await bridge.cancel_task("nonexistent")


class TestGetTaskStatus:
    """Tests for get_task_status."""

    def test_get_task_status(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-s"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": "sess-123",
            "output_buf": [],
            "output_len": 0,
        }

        status = bridge.get_task_status("task-s")
        assert status["status"] == "running"
        assert status["session_id"] == "sess-123"

    def test_get_task_status_not_found(self):
        bridge = ClaudeCodeBridge()
        status = bridge.get_task_status("nonexistent")
        assert status["status"] == "not_found"


class TestHandleEvent:
    """Tests for _handle_event."""

    @pytest.mark.asyncio
    async def test_handle_event_text(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-e"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        on_output = AsyncMock()
        on_question = AsyncMock()

        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Hello, I will fix the bug."}
                ]
            }
        }

        await bridge._handle_event("task-e", event, on_output, on_question)

        on_output.assert_called_once_with("task-e", "Hello, I will fix the bug.")
        assert bridge._tasks["task-e"]["output_buf"] == ["Hello, I will fix the bug."]

    @pytest.mark.asyncio
    async def test_handle_event_ask_user_question(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-q"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        on_output = AsyncMock()
        on_question = AsyncMock()

        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "AskUserQuestion",
                        "id": "tool-123",
                        "input": {"question": "Which file should I modify?"},
                    }
                ]
            }
        }

        await bridge._handle_event("task-q", event, on_output, on_question)

        on_question.assert_called_once_with("task-q", "Which file should I modify?", "tool-123")
        assert bridge._tasks["task-q"]["status"] == TaskStatus.WAITING_FOR_ANSWER

    @pytest.mark.asyncio
    async def test_handle_event_result(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-r"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        on_output = AsyncMock()
        on_question = AsyncMock()

        event = {
            "type": "result",
            "result": "Task completed successfully",
            "session_id": "sess-456",
        }

        await bridge._handle_event("task-r", event, on_output, on_question)

        assert bridge._tasks["task-r"]["session_id"] == "sess-456"
        assert "Task completed successfully" in bridge._tasks["task-r"]["output_buf"]

    @pytest.mark.asyncio
    async def test_handle_event_unknown_type(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-u"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        on_output = AsyncMock()
        on_question = AsyncMock()

        event = {"type": "unknown_event"}
        await bridge._handle_event("task-u", event, on_output, on_question)

        on_output.assert_not_called()
        on_question.assert_not_called()


class TestOutputTruncation:
    """Tests for output truncation protection."""

    def test_output_truncation(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-t"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        # Append text that exceeds MAX_OUTPUT_LEN
        large_text = "x" * (ClaudeCodeBridge.MAX_OUTPUT_LEN + 100)
        bridge._append_output("task-t", large_text)

        # First append should succeed (output_len was 0 < MAX_OUTPUT_LEN)
        assert len(bridge._tasks["task-t"]["output_buf"]) == 1

        # Second append should be skipped (output_len now >= MAX_OUTPUT_LEN)
        bridge._append_output("task-t", "more text")
        assert len(bridge._tasks["task-t"]["output_buf"]) == 1

    def test_collect_output_truncation(self):
        bridge = ClaudeCodeBridge()
        bridge._tasks["task-ct"] = {
            "process": MagicMock(),
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        # Fill buffer with large content
        large_text = "x" * (ClaudeCodeBridge.MAX_OUTPUT_LEN + 500)
        bridge._tasks["task-ct"]["output_buf"].append(large_text)
        bridge._tasks["task-ct"]["output_len"] = len(large_text)

        result = bridge._collect_output("task-ct")
        assert len(result) <= ClaudeCodeBridge.MAX_OUTPUT_LEN + 200  # Allow for truncation message
        assert "truncated" in result
