"""Tests for the parser registry."""

import pytest

from codercrucible.parsers import (
    ParserRegistry,
    create_parser,
    list_available_parsers,
    register,
)


# Test parser for registry tests
@register("test")
class TestParser:
    """Test parser for registry tests."""

    agent_name = "test"

    def discover(self):
        return [{"id": "test-session-1", "timestamp": "2024-01-01"}]

    def parse(self, session_id):
        return {"session_id": session_id, "parsed": True}


class TestParserRegistry:
    """Tests for ParserRegistry class."""

    def test_register_parser(self):
        """Test that a parser can be registered."""
        # test parser is already registered via decorator above
        assert "test" in ParserRegistry._parsers

    def test_get_parser(self):
        """Test getting a parser by name."""
        parser_class = ParserRegistry.get("test")
        assert parser_class is not None
        assert parser_class.agent_name == "test"

    def test_get_nonexistent_parser(self):
        """Test getting a parser that doesn't exist returns None."""
        result = ParserRegistry.get("nonexistent")
        assert result is None

    def test_list_parsers(self):
        """Test listing all registered parsers."""
        parsers = ParserRegistry.list_parsers()
        assert "test" in parsers
        assert "claude" in parsers
        assert "cursor" in parsers

    def test_create_parser(self):
        """Test creating a parser instance."""
        parser = ParserRegistry.create("test")
        assert parser is not None
        assert isinstance(parser, TestParser)

    def test_create_nonexistent_parser(self):
        """Test creating a nonexistent parser returns None."""
        result = ParserRegistry.create("nonexistent")
        assert result is None


class TestRegisterDecorator:
    """Tests for the register decorator."""

    def test_register_function(self):
        """Test that register is the same as ParserRegistry.register."""
        assert register == ParserRegistry.register


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_parser(self):
        """Test create_parser helper function."""
        parser = create_parser("test")
        assert parser is not None
        assert parser.agent_name == "test"

    def test_create_parser_nonexistent(self):
        """Test create_parser with nonexistent agent."""
        result = create_parser("nonexistent-agent-xyz")
        assert result is None

    def test_list_available_parsers(self):
        """Test list_available_parsers helper function."""
        parsers = list_available_parsers()
        assert isinstance(parsers, list)
        assert len(parsers) > 0
        assert "claude" in parsers


class TestClaudeParserRegistration:
    """Tests that Claude parser is properly registered."""

    def test_claude_parser_registered(self):
        """Test that Claude parser is registered."""
        assert "claude" in ParserRegistry._parsers

    def test_get_claude_parser(self):
        """Test getting the Claude parser."""
        parser_class = ParserRegistry.get("claude")
        assert parser_class is not None

    def test_create_claude_parser(self):
        """Test creating a Claude parser instance."""
        parser = create_parser("claude")
        assert parser is not None
        assert parser.agent_name == "claude"


class TestCursorParserRegistration:
    """Tests that Cursor parser is properly registered."""

    def test_cursor_parser_registered(self):
        """Test that Cursor parser is registered."""
        assert "cursor" in ParserRegistry._parsers

    def test_get_cursor_parser(self):
        """Test getting the Cursor parser."""
        parser_class = ParserRegistry.get("cursor")
        assert parser_class is not None
