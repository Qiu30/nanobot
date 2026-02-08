"""Claude Code tool for delegating development tasks to Claude Code CLI."""

import asyncio
import uuid
from typing import Any, Callable, Awaitable

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.bridge.claude_code import ClaudeCodeBridge
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


class ClaudeCodeTool(Tool):
    """
    Tool to delegate development tasks to Claude Code CLI.

    Starts a background Claude Code process, streams output to the user,
    and routes AskUserQuestion prompts back to the user via the message bus.
    """

    def __init__(self, bridge: ClaudeCodeBridge, bus: MessageBus):
        self._bridge = bridge
        self._bus = bus
        self._channel = "cli"
        self._chat_id = "direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current message context for routing output."""
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def description(self) -> str:
        return (
            "Delegate a development task to Claude Code. "
            "Claude Code will work on the task in the background and report results. "
            "If it needs clarification, it will ask the user directly."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "The development task or requirement for Claude Code",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the task",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model to use: 'opus' (best quality, slower, expensive), 'sonnet' (balanced, default), or 'haiku' (fast, cheap)",
                    "enum": ["opus", "sonnet", "haiku"],
                },
            },
            "required": ["requirement"],
        }

    async def execute(self, requirement: str, working_dir: str | None = None, model: str | None = None, **kwargs: Any) -> str:
        """Start a Claude Code task in the background."""
        task_id = str(uuid.uuid4())[:8]
        channel = self._channel
        chat_id = self._chat_id

        # Build context key for session reuse
        context_key = f"{channel}:{chat_id}"

        # Map model shortcuts to full model names
        model_map = {
            "opus": "claude-opus-4-6",
            "sonnet": "claude-sonnet-4-5-20250929",
            "haiku": "claude-haiku-4-5-20251001",
        }
        selected_model = model_map.get(model) if model else None

        async def on_output(tid: str, text: str) -> None:
            """Forward Claude Code text output to the user."""
            # Only forward substantial output, skip tiny fragments
            if len(text.strip()) < 5:
                return
            await self._bus.publish_outbound(OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=f"[Claude Code] {text}",
            ))

        async def on_question(tid: str, question: str, tool_use_id: str) -> None:
            """Forward Claude Code's question to the user."""
            await self._bus.publish_outbound(OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=f"[Claude Code needs your input]\n{question}\n\n(Reply to answer)",
            ))

        async def on_complete(tid: str, result: str) -> None:
            """Announce task completion via the message bus."""
            status = self._bridge.get_task_status(tid).get("status", "unknown")
            status_label = "completed" if status == "completed" else "finished"

            announce = f"""[Claude Code task {status_label}]

Result:
{result[:3000]}"""

            msg = InboundMessage(
                channel="system",
                sender_id="claude_code",
                chat_id=f"{channel}:{chat_id}",
                content=announce,
            )
            await self._bus.publish_inbound(msg)

        try:
            await self._bridge.start_task(
                task_id=task_id,
                requirement=requirement,
                on_output=on_output,
                on_question=on_question,
                on_complete=on_complete,
                model=selected_model,
                context_key=context_key,
            )

            # Get session info for user feedback
            task_status = self._bridge.get_task_status(task_id)
            session_id = task_status.get("session_id")

            model_info = f" using {model} model" if model else ""
            session_info = f" (session: {session_id[:8]}...)" if session_id else " (new session)"

            logger.info(f"Claude Code task [{task_id}] started for {context_key}{model_info}{session_info}")
            return f"Claude Code task started (id: {task_id}){model_info}{session_info}. I'll notify you when it completes or if it needs input."
        except Exception as e:
            return f"Error starting Claude Code task: {e}"

    def clear_session(self, channel: str | None = None, chat_id: str | None = None) -> str:
        """
        Clear the session for a specific context or the current context.

        Args:
            channel: Optional channel to clear. If None, uses current channel.
            chat_id: Optional chat_id to clear. If None, uses current chat_id.

        Returns:
            Status message indicating whether the session was cleared.
        """
        target_channel = channel or self._channel
        target_chat_id = chat_id or self._chat_id
        context_key = f"{target_channel}:{target_chat_id}"

        cleared = self._bridge.clear_session(context_key)
        if cleared:
            logger.info(f"Cleared session for context {context_key}")
            return f"Session cleared for {context_key}"
        else:
            return f"No active session found for {context_key}"

    def get_session_info(self, channel: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
        """
        Get session information for a specific context or the current context.

        Args:
            channel: Optional channel to query. If None, uses current channel.
            chat_id: Optional chat_id to query. If None, uses current chat_id.

        Returns:
            Dictionary with session information including session_id and last_used timestamp.
        """
        target_channel = channel or self._channel
        target_chat_id = chat_id or self._chat_id
        context_key = f"{target_channel}:{target_chat_id}"

        session_id = self._bridge.get_session_id(context_key)
        if session_id:
            return {
                "context_key": context_key,
                "session_id": session_id,
                "has_session": True,
            }
        else:
            return {
                "context_key": context_key,
                "session_id": None,
                "has_session": False,
            }

