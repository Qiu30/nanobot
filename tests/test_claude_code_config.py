"""Tests for ClaudeCodeConfig."""

from nanobot.config.schema import ClaudeCodeConfig, ToolsConfig


class TestClaudeCodeConfig:
    """Tests for ClaudeCodeConfig defaults."""

    def test_claude_code_config_defaults(self):
        config = ClaudeCodeConfig()
        assert config.enabled is False
        assert config.command == "claude"
        assert config.allowed_tools == []
        assert config.model == ""

    def test_claude_code_config_custom(self):
        config = ClaudeCodeConfig(
            enabled=True,
            command="/usr/bin/claude",
            allowed_tools=["Read", "Write"],
            model="claude-opus-4-6",
        )
        assert config.enabled is True
        assert config.command == "/usr/bin/claude"
        assert config.allowed_tools == ["Read", "Write"]
        assert config.model == "claude-opus-4-6"


class TestToolsConfig:
    """Tests for ToolsConfig containing claude_code."""

    def test_tools_config_has_claude_code(self):
        config = ToolsConfig()
        assert hasattr(config, "claude_code")
        assert isinstance(config.claude_code, ClaudeCodeConfig)
        assert config.claude_code.enabled is False
