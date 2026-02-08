"""QQ channel implementation using OneBot 11 protocol."""

import asyncio
import json
import re
from typing import Any

from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import QQConfig


class QQChannel(BaseChannel):
    """
    QQ channel that connects to OneBot 11 protocol implementation.

    OneBot 11 is a standard protocol for QQ bot implementations.
    Communication is via WebSocket using JSON format.
    """

    name = "qq"

    def __init__(self, config: QQConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: QQConfig = config
        self._ws = None
        self._connected = False

    async def start(self) -> None:
        """Start the QQ channel by connecting to OneBot server."""
        import websockets

        ws_url = self.config.ws_url

        logger.info(f"Connecting to OneBot server at {ws_url}...")

        self._running = True

        while self._running:
            try:
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("Connected to OneBot server")

                    # Listen for messages
                    async for message in ws:
                        try:
                            await self._handle_onebot_message(message)
                        except Exception as e:
                            logger.error(f"Error handling OneBot message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning(f"OneBot connection error: {e}")

                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the QQ channel."""
        self._running = False
        self._connected = False
        # WebSocket will be closed automatically by context manager
        self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through QQ."""
        if not self._ws or not self._connected:
            logger.warning("OneBot server not connected")
            return

        try:
            # Parse chat_id to determine message type
            # Format: "private:{user_id}" or "group:{group_id}"
            message_type = "private"
            target_id = msg.chat_id

            if ":" in msg.chat_id:
                parts = msg.chat_id.split(":", 1)
                message_type = parts[0]
                target_id = parts[1]

            # Build OneBot API request
            payload = {
                "action": "send_msg",
                "params": {
                    "message_type": message_type,
                    "message": msg.content
                }
            }

            # Add target ID based on message type
            if message_type == "private":
                payload["params"]["user_id"] = int(target_id)
            elif message_type == "group":
                payload["params"]["group_id"] = int(target_id)

            await self._ws.send(json.dumps(payload))
            logger.debug(f"Sent message to {message_type}:{target_id}")

        except Exception as e:
            logger.error(f"Error sending QQ message: {e}")

    async def _handle_onebot_message(self, raw: str) -> None:
        """Handle a message from OneBot server."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from OneBot: {raw[:100]}")
            return

        post_type = data.get("post_type")

        if post_type == "message":
            # Incoming message from QQ
            message_type = data.get("message_type")  # private or group
            user_id = str(data.get("user_id", ""))
            raw_message = data.get("raw_message", "")

            # Parse CQ codes to plain text
            content = self._parse_cq_code(raw_message)

            # Build chat_id based on message type
            if message_type == "private":
                chat_id = f"private:{user_id}"
            elif message_type == "group":
                group_id = str(data.get("group_id", ""))
                chat_id = f"group:{group_id}"
            else:
                logger.warning(f"Unknown message type: {message_type}")
                return

            await self._handle_message(
                sender_id=user_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "message_id": data.get("message_id"),
                    "time": data.get("time"),
                    "message_type": message_type,
                    "raw_message": raw_message
                }
            )

        elif post_type == "meta_event":
            # Meta events (heartbeat, lifecycle, etc.)
            meta_event_type = data.get("meta_event_type")
            if meta_event_type == "heartbeat":
                logger.debug("Received heartbeat from OneBot")
            elif meta_event_type == "lifecycle":
                sub_type = data.get("sub_type")
                logger.info(f"OneBot lifecycle event: {sub_type}")

        elif post_type == "notice":
            # Notice events (group member changes, etc.)
            notice_type = data.get("notice_type")
            logger.debug(f"Received notice: {notice_type}")

        elif post_type == "request":
            # Request events (friend requests, group invitations, etc.)
            request_type = data.get("request_type")
            logger.info(f"Received request: {request_type}")

    def _parse_cq_code(self, text: str) -> str:
        """
        Parse CQ codes in message to plain text.

        CQ codes are special markup used by OneBot protocol.
        Examples:
        - [CQ:at,qq=123456] -> @123456
        - [CQ:face,id=178] -> [表情178]
        - [CQ:image,file=xxx.jpg] -> [图片]
        """
        # Handle @mentions
        text = re.sub(r'\[CQ:at,qq=(\d+)\]', r'@\1', text)

        # Handle images
        text = re.sub(r'\[CQ:image,[^\]]+\]', '[图片]', text)

        # Handle faces/emojis
        text = re.sub(r'\[CQ:face,id=(\d+)\]', r'[表情\1]', text)

        # Handle voice messages
        text = re.sub(r'\[CQ:record,[^\]]+\]', '[语音]', text)

        # Handle videos
        text = re.sub(r'\[CQ:video,[^\]]+\]', '[视频]', text)

        # Handle other CQ codes generically
        text = re.sub(r'\[CQ:([^,\]]+),[^\]]+\]', r'[\1]', text)

        return text
