"""Tests for codercrucible.parsers.cursor — Cursor parser."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from codercrucible.parsers.base import ParserRegistry, create_parser, list_available_parsers
from codercrucible.parsers.cursor import CursorParser
from codercrucible.parsers import utils
from codercrucible.parsers import cursor as cursor_module


class TestParserRegistry:
    """Tests for the parser registry."""

    def test_register_and_get(self):
        """Test registering and retrieving a parser."""
        parser_class = ParserRegistry.get("cursor")
        assert parser_class is not None
        assert parser_class == CursorParser

    def test_list_parsers(self):
        """Test listing available parsers."""
        parsers = list_available_parsers()
        assert "cursor" in parsers

    def test_create_parser(self):
        """Test creating a parser instance."""
        parser = create_parser("cursor")
        assert parser is not None
        assert isinstance(parser, CursorParser)
        assert parser.agent_name == "cursor"

    def test_create_unknown_parser(self):
        """Test creating an unknown parser returns None."""
        parser = create_parser("unknown_agent")
        assert parser is None


class TestCursorParserBasics:
    """Basic tests for the Cursor parser."""

    def test_agent_name(self):
        """Test agent name property."""
        parser = CursorParser()
        assert parser.agent_name == "cursor"

    def test_get_storage_paths(self):
        """Test storage paths method."""
        parser = CursorParser()
        paths = parser.get_storage_paths()
        assert isinstance(paths, list)

    def test_discover_empty_db(self):
        """Test discover with an empty database."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                sessions = parser.discover()
                assert sessions == []

    def test_discover_with_sessions(self):
        """Test discover with sample session data."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {
                "sessionId": "test-session-123",
                "timestamp": 1706000000000,
                "messages": [
                    {"role": "user", "content": "Hello", "timestamp": 1706000000000},
                    {"role": "assistant", "content": "Hi there!", "timestamp": 1706000001000},
                ],
            }
            
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"composerData:test-session-123", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                sessions = parser.discover()
                assert len(sessions) == 1
                assert sessions[0]["session_id"] == "test-session-123"
                assert "timestamp" in sessions[0]

    def test_discover_bubble_id_sessions(self):
        """Test discover with bubbleId prefix."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {
                "sessionId": "bubble-session-456",
                "createdAt": "2024-01-23T10:00:00Z",
            }
            
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"bubbleId:bubble-session-456", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                sessions = parser.discover()
                assert len(sessions) == 1
                assert sessions[0]["session_id"] == "bubble-session-456"

    def test_parse_session(self):
        """Test parsing a session."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {
                "sessionId": "test-session-789",
                "model": "claude-3-opus",
                "timestamp": 1706000000000,
                "messages": [
                    {
                        "role": "user",
                        "content": "Write a hello world program",
                        "timestamp": 1706000000000
                    },
                    {
                        "role": "assistant",
                        "content": "Here's a hello world program:",
                        "timestamp": 1706000001000,
                        "tool_calls": [
                            {"name": "Write", "input": {"file_path": "main.py", "content": "print('Hello, World!')"}}
                        ]
                    },
                ],
            }
            
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"composerData:test-session-789", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                result = parser.parse("test-session-789")
                
                assert result is not None
                assert result["session_id"] == "test-session-789"
                assert result["model"] == "claude-3-opus"
                assert len(result["messages"]) == 2
                assert result["messages"][0]["role"] == "user"
                assert result["messages"][1]["role"] == "assistant"
                assert "tool_uses" in result["messages"][1]
                assert result["stats"]["user_messages"] == 1
                assert result["stats"]["assistant_messages"] == 1

    def test_parse_nonexistent_session(self):
        """Test parsing a session that doesn't exist."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                result = parser.parse("nonexistent-session")
                assert result is None


class TestParserUtils:
    """Tests for parser utilities."""

    def test_temp_copy(self):
        """Test temp_copy utility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "test.txt"
            src.write_text("test content")
            
            temp_path = utils.temp_copy(src)
            
            assert temp_path.exists()
            assert temp_path.read_text() == "test content"
            
            temp_path.unlink()

    def test_temp_copy_nonexistent(self):
        """Test temp_copy with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            utils.temp_copy("/nonexistent/file.txt")

    def test_normalise_path_with_home(self):
        """Test path normalisation with home directory."""
        home = Path.home()
        test_path = home / "Documents" / "project" / "file.txt"
        
        result = utils.normalise_path(test_path)
        
        assert result.startswith("~/")

    def test_normalise_path_relative(self):
        """Test path normalisation with project root."""
        home = Path.home()
        project_root = home / "Documents" / "project"
        test_path = project_root / "src" / "main.py"
        
        result = utils.normalise_path(test_path, project_root=project_root)
        
        # When path is under project_root, should return relative path
        # Note: the home replacement takes precedence over relative path
        assert "src/main.py" in result

    def test_extract_timestamp_iso(self):
        """Test extracting timestamp from ISO string."""
        ts = "2025-01-15T10:00:00+00:00"
        result = utils.extract_timestamp(ts)
        
        assert result is not None
        assert isinstance(result, float)

    def test_extract_timestamp_none(self):
        """Test extracting timestamp from None."""
        result = utils.extract_timestamp(None)
        assert result is None

    def test_extract_timestamp_invalid(self):
        """Test extracting timestamp from invalid string."""
        result = utils.extract_timestamp("not-a-timestamp")
        assert result is None


class TestTimestampExtraction:
    """Tests for timestamp extraction from Cursor session data."""

    def test_extract_timestamp_from_data(self):
        """Test extracting timestamp from session data."""
        parser = CursorParser()
        
        data = {"timestamp": 1706000000000}
        result = parser._extract_timestamp_from_data(data)
        
        assert result is not None
        assert "T" in result

    def test_extract_timestamp_from_created_at(self):
        """Test extracting timestamp from createdAt field."""
        parser = CursorParser()
        
        data = {"createdAt": "2024-01-23T10:00:00Z"}
        result = parser._extract_timestamp_from_data(data)
        
        assert result is not None
        assert "2024" in result


class TestMessageParsing:
    """Tests for message extraction and parsing."""

    def test_parse_user_message(self):
        """Test parsing a user message."""
        parser = CursorParser()
        
        msg = {
            "role": "user",
            "content": "Hello, how are you?",
            "timestamp": 1706000000000
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert result["role"] == "user"
        assert result["content"] == "Hello, how are you?"

    def test_parse_assistant_message(self):
        """Test parsing an assistant message."""
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": "I'm doing well, thank you!",
            "timestamp": 1706000000000
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert result["role"] == "assistant"
        assert result["content"] == "I'm doing well, thank you!"

    def test_parse_message_with_thinking(self):
        """Test parsing a message with thinking."""
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": "Let me think about this.",
            "thinking": "The user is asking about...",
            "timestamp": 1706000000000
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert "thinking" in result
        assert result["thinking"] == "The user is asking about..."

    def test_parse_message_with_tool_calls(self):
        """Test parsing a message with tool calls."""
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": "I'll read that file.",
            "tool_calls": [
                {"name": "Read", "input": {"file_path": "src/main.py"}}
            ],
            "timestamp": 1706000000000
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert "tool_uses" in result
        assert len(result["tool_uses"]) == 1
        assert result["tool_uses"][0]["tool"] == "Read"

    def test_parse_empty_message(self):
        """Test parsing an empty message returns None."""
        parser = CursorParser()
        
        msg = {"role": "user", "content": ""}
        
        result = parser._parse_message(msg)
        
        assert result is None


class TestStatsComputation:
    """Tests for statistics computation."""

    def test_compute_stats(self):
        """Test computing session statistics."""
        parser = CursorParser()
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Help me"},
            {"role": "assistant", "content": "Sure", "tool_uses": [{"tool": "Read", "input": {}}]},
        ]
        
        stats = parser._compute_stats(messages)
        
        assert stats["user_messages"] == 2
        assert stats["assistant_messages"] == 2
        assert stats["tool_uses"] == 1

    def test_compute_stats_empty(self):
        """Test computing stats for empty messages."""
        parser = CursorParser()
        
        stats = parser._compute_stats([])
        
        assert stats["user_messages"] == 0
        assert stats["assistant_messages"] == 0
        assert stats["tool_uses"] == 0
