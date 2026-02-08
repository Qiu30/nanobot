"""Claude Code CLI bridge for running tasks via claude subprocess."""

import asyncio
import json
import sys
import uuid
from enum import Enum
from typing import Any, Callable, Awaitable

from loguru import logger


class TaskStatus(Enum):
    """Status of a Claude Code task."""
    RUNNING = "running"
    WAITING_FOR_ANSWER = "waiting_for_answer"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClaudeCodeBridge:
    """
    Bridge to Claude Code CLI.

    Starts claude as a subprocess with stream-json I/O,
    parses events, detects AskUserQuestion tool calls,
    and manages concurrent tasks.
    """

    MAX_OUTPUT_LEN = 50000  # Truncate output beyond this length

    def __init__(
        self,
        claude_bin: str = "claude",
        working_dir: str | None = None,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
    ):
        self._claude_bin = claude_bin
        self._working_dir = working_dir
        self._allowed_tools: list[str] = allowed_tools or []
        self._model = model
        self._tasks: dict[str, dict[str, Any]] = {}

    async def start_task(
        self,
        task_id: str,
        requirement: str,
        on_output: Callable[[str, str], Awaitable[None]],
        on_question: Callable[[str, str, str], Awaitable[None]],
        on_complete: Callable[[str, str], Awaitable[None]],
        model: str | None = None,
    ) -> None:
        """
        Start a new Claude Code task.

        Args:
            task_id: Unique task identifier.
            requirement: The task requirement/prompt.
            on_output: Callback(task_id, text) for assistant text output.
            on_question: Callback(task_id, question, tool_use_id) when user input needed.
            on_complete: Callback(task_id, result) when task finishes.
            model: Optional model override for this task.
        """
        if task_id in self._tasks:
            raise ValueError(f"Task {task_id} already exists")

        # Temporarily override model if specified
        original_model = self._model
        if model:
            self._model = model

        cmd = self._build_command()
        logger.info(f"Claude task [{task_id}] starting: {requirement[:80]}")

        # Restore original model
        self._model = original_model

        # On Windows, use shell mode if path contains spaces
        is_windows = sys.platform == "win32"
        use_shell = is_windows and " " in self._claude_bin

        if use_shell:
            # Build command string with proper quoting for Windows shell
            cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd)
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_dir,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_dir,
            )

        self._tasks[task_id] = {
            "process": process,
            "status": TaskStatus.RUNNING,
            "session_id": None,
            "output_buf": [],
            "output_len": 0,
        }

        # Send the initial prompt via stream-json stdin
        await self._send_stdin(process, {
            "type": "user",
            "message": {
                "role": "user",
                "content": requirement,
            },
        })

        # Start reading stdout in background
        asyncio.create_task(
            self._read_stream(task_id, process, on_output, on_question, on_complete)
        )

    async def send_answer(self, task_id: str, answer: str) -> None:
        """Send a user answer to a waiting task."""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task["status"] != TaskStatus.WAITING_FOR_ANSWER:
            raise ValueError(f"Task {task_id} is not waiting for an answer (status: {task['status'].value})")

        process = task["process"]
        await self._send_stdin(process, {
            "type": "user",
            "message": {
                "role": "user",
                "content": answer,
            },
        })
        task["status"] = TaskStatus.RUNNING
        logger.info(f"Claude task [{task_id}] answer sent")

    async def cancel_task(self, task_id: str) -> None:
        """Cancel a running task."""
        task = self._tasks.get(task_id)
        if not task:
            return

        process = task["process"]
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()

        task["status"] = TaskStatus.CANCELLED
        logger.info(f"Claude task [{task_id}] cancelled")

    def get_task_status(self, task_id: str) -> dict:
        """Get the status of a task."""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "not_found"}
        return {
            "status": task["status"].value,
            "session_id": task["session_id"],
        }

    def _build_command(self) -> list[str]:
        """Build the claude CLI command."""
        cmd = [
            self._claude_bin, "-p",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--verbose",
        ]
        if self._model:
            cmd.extend(["--model", self._model])
        if self._allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self._allowed_tools)])
        else:
            cmd.append("--dangerously-skip-permissions")
        return cmd

    async def _send_stdin(self, process: asyncio.subprocess.Process, data: dict) -> None:
        """Write a JSON line to the process stdin."""
        if process.stdin is None:
            return
        line = json.dumps(data, ensure_ascii=False) + "\n"
        process.stdin.write(line.encode("utf-8"))
        await process.stdin.drain()

    async def _read_stream(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        on_output: Callable[[str, str], Awaitable[None]],
        on_question: Callable[[str, str, str], Awaitable[None]],
        on_complete: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Read and parse the stream-json output from claude."""
        task = self._tasks.get(task_id)
        if not task or process.stdout is None:
            return

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    logger.debug(f"Claude task [{task_id}] non-JSON line: {text[:200]}")
                    continue

                await self._handle_event(task_id, event, on_output, on_question)

            # Process ended
            await process.wait()

            result = self._collect_output(task_id)

            # Read stderr for error info
            if process.returncode != 0 and process.stderr:
                stderr_data = await process.stderr.read()
                stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
                if stderr_text:
                    result += f"\n\nSTDERR:\n{stderr_text}"
                task["status"] = TaskStatus.FAILED
            elif task["status"] == TaskStatus.RUNNING:
                task["status"] = TaskStatus.COMPLETED

            logger.info(f"Claude task [{task_id}] finished with status {task['status'].value}")
            await on_complete(task_id, result)

        except Exception as e:
            logger.error(f"Claude task [{task_id}] stream error: {e}")
            task["status"] = TaskStatus.FAILED
            await on_complete(task_id, f"Error: {e}")

    async def _handle_event(
        self,
        task_id: str,
        event: dict,
        on_output: Callable[[str, str], Awaitable[None]],
        on_question: Callable[[str, str, str], Awaitable[None]],
    ) -> None:
        """Handle a single stream-json event."""
        task = self._tasks.get(task_id)
        if not task:
            return

        event_type = event.get("type")

        if event_type == "assistant":
            message = event.get("message", {})
            content_blocks = message.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    self._append_output(task_id, text)
                    await on_output(task_id, text)

                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "")
                    if tool_name == "AskUserQuestion":
                        question = block.get("input", {}).get("question", "")
                        tool_use_id = block.get("id", "")
                        task["status"] = TaskStatus.WAITING_FOR_ANSWER
                        logger.info(f"Claude task [{task_id}] asking: {question[:100]}")
                        await on_question(task_id, question, tool_use_id)

        elif event_type == "result":
            result_text = event.get("result", "")
            session_id = event.get("session_id")
            if session_id:
                task["session_id"] = session_id
            if result_text:
                self._append_output(task_id, result_text)

    def _append_output(self, task_id: str, text: str) -> None:
        """Append text to task output buffer with truncation protection."""
        task = self._tasks.get(task_id)
        if not task:
            return
        if task["output_len"] < self.MAX_OUTPUT_LEN:
            task["output_buf"].append(text)
            task["output_len"] += len(text)

    def _collect_output(self, task_id: str) -> str:
        """Collect all buffered output for a task."""
        task = self._tasks.get(task_id)
        if not task:
            return ""
        result = "\n".join(task["output_buf"])
        if len(result) > self.MAX_OUTPUT_LEN:
            result = result[:self.MAX_OUTPUT_LEN] + f"\n... (truncated, {len(result) - self.MAX_OUTPUT_LEN} more chars)"
        return result
