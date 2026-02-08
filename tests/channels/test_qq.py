"""Tests for QQ channel implementation using OneBot 11 protocol."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.qq import QQChannel
from nanobot.config.schema import QQConfig


@pytest.fixture
def qq_config():
    """Create a test QQ config."""
    return QQConfig(
        enabled=True,
        ws_url="ws://localhost:8080",
        allow_from=["123456", "789012"]
    )


@pytest.fixture
def message_bus():
    """Create a test message bus."""
    return MessageBus()


@pytest.fixture
def qq_channel(qq_config, message_bus):
    """Create a test QQ channel."""
    return QQChannel(qq_config, message_bus)


class TestQQChannelBasic:
    """Test basic QQ channel functionality."""

    async def test_channel_initialization(self, qq_channel, qq_config):
        """Test that channel initializes correctly."""
        assert qq_channel.name == "qq"
        assert qq_channel.config == qq_config
        assert not qq_channel.is_running

    async def test_channel_start_stop(self, qq_channel):
        """Test starting and stopping the channel."""
        assert not qq_channel.is_running

        await qq_channel.start()
        assert qq_channel.is_running

        await qq_channel.stop()
        assert not qq_channel.is_running

    async def test_allow_list_empty(self):
        """Test that empty allow list allows everyone."""
        config = QQConfig(enabled=True, ws_url="ws://localhost:8080", allow_from=[])
        bus = MessageBus()
        channel = QQChannel(config, bus)

        assert channel.is_allowed("123456")
        assert channel.is_allowed("999999")

    async def test_allow_list_filtering(self, qq_channel):
        """Test that allow list filters correctly."""
        assert qq_channel.is_allowed("123456")
        assert qq_channel.is_allowed("789012")
        assert not qq_channel.is_allowed("999999")


class TestQQChannelWebSocket:
    """Test QQ channel WebSocket connection."""

    @patch('websockets.connect')
    async def test_websocket_connection_success(self, mock_connect, qq_channel):
        """Test successful WebSocket connection to NapCat."""
        # Create a mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = []  # No messages
        mock_connect.return_value.__aenter__.return_value = mock_ws

        # Start channel in background
        task = asyncio.create_task(qq_channel.start())
        await asyncio.sleep(0.1)  # Let it connect

        # Verify connection was attempted
        mock_connect.assert_called_once_with(qq_channel.config.ws_url)
        assert qq_channel._connected

        # Stop channel
        await qq_channel.stop()
        await task

    @patch('websockets.connect')
    async def test_websocket_reconnection(self, mock_connect, qq_channel):
        """Test WebSocket reconnection on disconnect."""
        # First connection fails, second succeeds
        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = []

        mock_connect.side_effect = [
            Exception("Connection failed"),
            AsyncMock(__aenter__=AsyncMock(return_value=mock_ws))
        ]

        # Start channel in background
        task = asyncio.create_task(qq_channel.start())
        await asyncio.sleep(0.1)  # Let it try first connection

        # Should have tried to connect
        assert mock_connect.call_count >= 1

        # Stop channel
        await qq_channel.stop()
        await task

    @patch('websockets.connect')
    async def test_websocket_error_handling(self, mock_connect, qq_channel):
        """Test WebSocket error handling."""
        # Connection always fails
        mock_connect.side_effect = Exception("Connection error")

        # Start channel in background
        task = asyncio.create_task(qq_channel.start())
        await asyncio.sleep(0.1)  # Let it try to connect

        # Should have tried to connect
        assert mock_connect.call_count >= 1
        assert not qq_channel._connected

        # Stop channel
        await qq_channel.stop()
        await task


class TestQQChannelMessageHandling:
    """Test QQ channel message handling."""

    async def test_handle_private_message(self, qq_channel, message_bus):
        """Test handling a private message from QQ."""
        # Mock OneBot message
        onebot_msg = {
            "post_type": "message",
            "message_type": "private",
            "user_id": 123456,
            "raw_message": "Hello, bot!",
            "message_id": 1001,
            "time": 1234567890
        }

        # Handle the message
        await qq_channel._handle_onebot_message(json.dumps(onebot_msg))

        # Verify message was published to bus
        assert message_bus.inbound_size == 1
        msg = await message_bus.consume_inbound()

        assert msg.channel == "qq"
        assert msg.sender_id == "123456"
        assert msg.chat_id == "private:123456"
        assert msg.content == "Hello, bot!"
        assert msg.metadata["message_type"] == "private"

    async def test_handle_group_message(self, qq_channel, message_bus):
        """Test handling a group message from QQ."""
        # Mock OneBot message
        onebot_msg = {
            "post_type": "message",
            "message_type": "group",
            "user_id": 123456,
            "group_id": 987654,
            "raw_message": "Hello, group!",
            "message_id": 1002,
            "time": 1234567890
        }

        # Handle the message
        await qq_channel._handle_onebot_message(json.dumps(onebot_msg))

        # Verify message was published to bus
        assert message_bus.inbound_size == 1
        msg = await message_bus.consume_inbound()

        assert msg.channel == "qq"
        assert msg.sender_id == "123456"
        assert msg.chat_id == "group:987654"
        assert msg.content == "Hello, group!"
        assert msg.metadata["message_type"] == "group"

    async def test_handle_message_with_cq_codes(self, qq_channel, message_bus):
        """Test handling a message with CQ codes."""
        # Mock OneBot message with CQ codes
        onebot_msg = {
            "post_type": "message",
            "message_type": "private",
            "user_id": 123456,
            "raw_message": "Hello [CQ:at,qq=789012] [CQ:face,id=1]",
            "message_id": 1003,
            "time": 1234567890
        }

        # Handle the message
        await qq_channel._handle_onebot_message(json.dumps(onebot_msg))

        # Verify CQ codes were parsed
        msg = await message_bus.consume_inbound()
        assert msg.content == "Hello @789012 [表情1]"

    async def test_handle_invalid_json(self, qq_channel, message_bus):
        """Test handling invalid JSON from OneBot."""
        # Invalid JSON should be logged and ignored
        await qq_channel._handle_onebot_message("invalid json {")

        # No message should be published
        assert message_bus.inbound_size == 0

    async def test_handle_meta_event(self, qq_channel, message_bus):
        """Test handling meta events (heartbeat, lifecycle)."""
        # Heartbeat event
        heartbeat = {
            "post_type": "meta_event",
            "meta_event_type": "heartbeat",
            "time": 1234567890
        }

        await qq_channel._handle_onebot_message(json.dumps(heartbeat))

        # Meta events should not create messages
        assert message_bus.inbound_size == 0

    @patch('websockets.connect')
    async def test_send_private_message(self, mock_connect, qq_channel):
        """Test sending a private message through QQ."""
        # Mock WebSocket
        mock_ws = AsyncMock()
        qq_channel._ws = mock_ws
        qq_channel._connected = True

        # Send message
        msg = OutboundMessage(
            channel="qq",
            chat_id="private:123456",
            content="Hello from bot!"
        )

        await qq_channel.send(msg)

        # Verify WebSocket send was called
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])

        assert sent_data["action"] == "send_msg"
        assert sent_data["params"]["message_type"] == "private"
        assert sent_data["params"]["user_id"] == 123456
        assert sent_data["params"]["message"] == "Hello from bot!"

    @patch('websockets.connect')
    async def test_send_group_message(self, mock_connect, qq_channel):
        """Test sending a group message through QQ."""
        # Mock WebSocket
        mock_ws = AsyncMock()
        qq_channel._ws = mock_ws
        qq_channel._connected = True

        # Send message
        msg = OutboundMessage(
            channel="qq",
            chat_id="group:987654",
            content="Hello group!"
        )

        await qq_channel.send(msg)

        # Verify WebSocket send was called
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])

        assert sent_data["action"] == "send_msg"
        assert sent_data["params"]["message_type"] == "group"
        assert sent_data["params"]["group_id"] == 987654
        assert sent_data["params"]["message"] == "Hello group!"

    async def test_send_when_not_connected(self, qq_channel):
        """Test sending message when not connected."""
        # Should not raise exception, just log warning
        msg = OutboundMessage(
            channel="qq",
            chat_id="private:123456",
            content="Test"
        )

        await qq_channel.send(msg)  # Should not raise


class TestQQChannelCQCode:
    """Test CQ code parsing and handling."""

    def test_parse_cq_at(self, qq_channel):
        """Test parsing CQ at code."""
        text = "Hello [CQ:at,qq=123456] how are you?"
        result = qq_channel._parse_cq_code(text)
        assert result == "Hello @123456 how are you?"

    def test_parse_cq_image(self, qq_channel):
        """Test parsing CQ image code."""
        text = "Check this out [CQ:image,file=xxx.jpg,url=http://example.com/img.jpg]"
        result = qq_channel._parse_cq_code(text)
        assert result == "Check this out [图片]"

    def test_parse_cq_face(self, qq_channel):
        """Test parsing CQ face code."""
        text = "I'm happy [CQ:face,id=178]"
        result = qq_channel._parse_cq_code(text)
        assert result == "I'm happy [表情178]"

    def test_parse_cq_voice(self, qq_channel):
        """Test parsing CQ voice code."""
        text = "Listen to this [CQ:record,file=voice.amr]"
        result = qq_channel._parse_cq_code(text)
        assert result == "Listen to this [语音]"

    def test_parse_cq_video(self, qq_channel):
        """Test parsing CQ video code."""
        text = "Watch this [CQ:video,file=video.mp4]"
        result = qq_channel._parse_cq_code(text)
        assert result == "Watch this [视频]"

    def test_parse_mixed_cq_codes(self, qq_channel):
        """Test parsing mixed text and CQ codes."""
        text = "Hello [CQ:at,qq=123456] [CQ:face,id=1] check [CQ:image,file=test.jpg]"
        result = qq_channel._parse_cq_code(text)
        assert result == "Hello @123456 [表情1] check [图片]"

    def test_parse_plain_text(self, qq_channel):
        """Test parsing plain text without CQ codes."""
        text = "Just a normal message"
        result = qq_channel._parse_cq_code(text)
        assert result == "Just a normal message"


class TestQQChannelIntegration:
    """Test QQ channel integration with MessageBus."""

    async def test_message_bus_integration(self, qq_channel, message_bus):
        """Test that messages are published to the bus."""
        # Create a mock inbound message
        test_msg = InboundMessage(
            channel="qq",
            sender_id="123456",
            chat_id="123456",
            content="Test message"
        )

        # Publish to bus
        await message_bus.publish_inbound(test_msg)

        # Verify message is in queue
        assert message_bus.inbound_size == 1

        # Consume and verify
        received = await message_bus.consume_inbound()
        assert received.channel == "qq"
        assert received.sender_id == "123456"
        assert received.content == "Test message"

    async def test_outbound_message_routing(self, qq_channel, message_bus):
        """Test that outbound messages are routed correctly."""
        # Create outbound message
        test_msg = OutboundMessage(
            channel="qq",
            chat_id="123456",
            content="Response message"
        )

        # Publish to bus
        await message_bus.publish_outbound(test_msg)

        # Verify message is in queue
        assert message_bus.outbound_size == 1

        # Consume and verify
        received = await message_bus.consume_outbound()
        assert received.channel == "qq"
        assert received.chat_id == "123456"
        assert received.content == "Response message"


class TestQQChannelConfig:
    """Test QQ channel configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = QQConfig()
        assert not config.enabled
        assert config.ws_url == "ws://localhost:8080"
        assert config.allow_from == []

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = QQConfig(
            enabled=True,
            ws_url="ws://192.168.1.100:8080",
            allow_from=["123456", "789012"]
        )
        assert config.enabled
        assert config.ws_url == "ws://192.168.1.100:8080"
        assert len(config.allow_from) == 2

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = QQConfig(
            enabled=True,
            ws_url="ws://localhost:8080"
        )
        assert config.enabled

        # Test with invalid URL format (should still accept as string)
        config = QQConfig(
            enabled=True,
            ws_url="invalid-url"
        )
        assert config.ws_url == "invalid-url"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
