"""Tests for codercrucible.parsers.cursor — Cursor parser."""

import json
import os
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


class TestDiscoverFromDb:
    """Tests for the _discover_from_db method."""

    def test_discover_from_db_with_composer_prefix(self):
        """Test discovering sessions with composerData prefix."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {"sessionId": "composer-session", "timestamp": 1706000000000}
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"composerData:composer-session", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            sessions = parser._discover_from_db(db_path, db_path)
            
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "composer-session"
            assert sessions[0]["db_key"] == "composerData:composer-session"

    def test_discover_from_db_with_bubble_prefix(self):
        """Test discovering sessions with bubbleId prefix."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {"sessionId": "bubble-session", "createdAt": "2024-01-23T10:00:00Z"}
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"bubbleId:bubble-session", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            sessions = parser._discover_from_db(db_path, db_path)
            
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "bubble-session"
            assert sessions[0]["db_key"] == "bubbleId:bubble-session"

    def test_discover_from_db_with_invalid_json(self):
        """Test discovering sessions with invalid JSON value."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            # Insert invalid JSON
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                ("composerData:invalid-json", "not valid json {")
            )
            conn.commit()
            conn.close()
            
            sessions = parser._discover_from_db(db_path, db_path)
            
            # Should still return the session, but with no timestamp
            assert len(sessions) == 1
            assert sessions[0]["timestamp"] is None

    def test_discover_from_db_missing_table(self):
        """Test discovering sessions when table doesn't exist."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            # Create empty database without the required table
            conn = sqlite3.connect(str(db_path))
            conn.close()
            
            sessions = parser._discover_from_db(db_path, db_path)
            
            # Should return empty list without raising
            assert sessions == []


class TestParseFromDb:
    """Tests for the _parse_from_db method."""

    def test_parse_from_db_found_composer(self):
        """Test parsing a session found with composerData prefix."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {
                "sessionId": "test-123",
                "model": "claude-3-opus",
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            }
            
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"composerData:test-123", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            result = parser._parse_from_db(db_path, "test-123")
            
            assert result is not None
            assert result["session_id"] == "test-123"
            assert result["model"] == "claude-3-opus"
            assert len(result["messages"]) == 2

    def test_parse_from_db_found_bubble(self):
        """Test parsing a session found with bubbleId prefix."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            session_data = {
                "sessionId": "bubble-456",
                "model": "claude-3-sonnet",
                "messages": [{"role": "user", "content": "Test"}],
            }
            
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                (f"bubbleId:bubble-456", json.dumps(session_data))
            )
            conn.commit()
            conn.close()
            
            result = parser._parse_from_db(db_path, "bubble-456")
            
            assert result is not None
            assert result["session_id"] == "bubble-456"

    def test_parse_from_db_not_found(self):
        """Test parsing a session that doesn't exist in the database."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            conn.commit()
            conn.close()
            
            result = parser._parse_from_db(db_path, "nonexistent")
            
            assert result is None


class TestParseSessionData:
    """Tests for the _parse_session_data method."""

    def test_parse_session_data_valid(self):
        """Test parsing valid session data."""
        parser = CursorParser()
        
        session_data = {
            "sessionId": "session-abc",
            "model": "claude-3-5-sonnet",
            "gitBranch": "main",
            "startTime": 1706000000000,
            "messages": [
                {"role": "user", "content": "Write code"},
                {"role": "assistant", "content": "Here is the code", "tool_calls": []},
            ],
        }
        
        json_blob = json.dumps(session_data)
        result = parser._parse_session_data("session-abc", json_blob)
        
        assert result is not None
        assert result["session_id"] == "session-abc"
        assert result["model"] == "claude-3-5-sonnet"
        assert result["git_branch"] == "main"
        assert len(result["messages"]) == 2

    def test_parse_session_data_invalid_json(self):
        """Test parsing with invalid JSON."""
        parser = CursorParser()
        
        result = parser._parse_session_data("test", "not valid json")
        
        assert result is None

    def test_parse_session_data_non_dict(self):
        """Test parsing when JSON is not a dict."""
        parser = CursorParser()
        
        result = parser._parse_session_data("test", json.dumps(["list", "not", "dict"]))
        
        assert result is None

    def test_parse_session_data_empty_messages(self):
        """Test parsing session data with no messages."""
        parser = CursorParser()
        
        session_data = {
            "sessionId": "empty-session",
            "model": "claude-3-opus",
        }
        
        json_blob = json.dumps(session_data)
        result = parser._parse_session_data("empty-session", json_blob)
        
        assert result is not None
        assert result["messages"] == []
        assert result["stats"]["user_messages"] == 0
        assert result["stats"]["assistant_messages"] == 0


class TestTimestampSortKey:
    """Tests for the _timestamp_sort_key function."""

    def test_sort_key_with_valid_timestamp(self):
        """Test sort key with valid timestamp."""
        from codercrucible.parsers.cursor import _timestamp_sort_key
        
        session = {"timestamp": "2024-01-15T10:00:00+00:00"}
        key = _timestamp_sort_key(session)
        
        assert key == "2024-01-15T10:00:00+00:00"

    def test_sort_key_with_none_timestamp(self):
        """Test sort key with None timestamp."""
        from codercrucible.parsers.cursor import _timestamp_sort_key
        
        session = {"timestamp": None}
        key = _timestamp_sort_key(session)
        
        assert key == ""

    def test_sort_key_with_missing_timestamp(self):
        """Test sort key when timestamp is missing."""
        from codercrucible.parsers.cursor import _timestamp_sort_key
        
        session = {"session_id": "abc"}
        key = _timestamp_sort_key(session)
        
        assert key == ""

    def test_sort_key_with_empty_timestamp(self):
        """Test sort key with empty string timestamp."""
        from codercrucible.parsers.cursor import _timestamp_sort_key
        
        session = {"timestamp": ""}
        key = _timestamp_sort_key(session)
        
        assert key == ""

    def test_sort_key_with_non_string_timestamp(self):
        """Test sort key with non-string timestamp."""
        from codercrucible.parsers.cursor import _timestamp_sort_key
        
        session = {"timestamp": 12345}
        key = _timestamp_sort_key(session)
        
        assert key == ""


class TestTimestampSorting:
    """Tests for timestamp sorting in discover method."""

    def test_discover_sorts_by_timestamp(self):
        """Test that discover sorts sessions by timestamp."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            # Insert sessions with different timestamps
            sessions_data = [
                ("session-old", {"timestamp": 1704000000000}),  # Older
                ("session-new", {"timestamp": 1707000000000}),  # Newer
                ("session-mid", {"timestamp": 1705500000000}),  # Middle
            ]
            
            for session_id, data in sessions_data:
                conn.execute(
                    "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                    (f"composerData:{session_id}", json.dumps(data))
                )
            
            conn.commit()
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                discovered = parser.discover()
                
                # Should be sorted newest first
                assert len(discovered) == 3
                assert discovered[0]["session_id"] == "session-new"
                assert discovered[1]["session_id"] == "session-mid"
                assert discovered[2]["session_id"] == "session-old"

    def test_discover_sorts_with_none_timestamps_at_end(self):
        """Test that sessions with None timestamps sort to the end."""
        parser = CursorParser()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.vscdb"
            
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
            
            # Insert sessions - one with timestamp, one without
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                ("composerData:session-with-time", json.dumps({"timestamp": 1706000000000}))
            )
            conn.execute(
                "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
                ("composerData:session-no-time", json.dumps({"other": "data"}))
            )
            
            conn.commit()
            conn.close()
            
            with patch.object(cursor_module, "get_cursor_db_paths", return_value=[db_path]):
                discovered = parser.discover()
                
                # Session with timestamp should come first
                assert len(discovered) == 2
                assert discovered[0]["session_id"] == "session-with-time"
                assert discovered[1]["session_id"] == "session-no-time"


class TestWindowsPath:
    """Tests for Windows path handling."""

    def test_get_windows_storage_path_with_appdata(self):
        """Test Windows storage path with APPDATA set."""
        # Save original state
        orig_environ = os.environ.copy()
        
        try:
            os.environ["APPDATA"] = "C:\\Users\\test\\AppData\\Roaming"
            
            from codercrucible.parsers.utils import _get_windows_storage_path
            
            path = _get_windows_storage_path()
            
            # Should return Windows path based on APPDATA
            assert "Cursor" in str(path)
            assert "AppData" in str(path)
            assert "Roaming" in str(path)
        finally:
            # Restore
            os.environ.clear()
            os.environ.update(orig_environ)

    def test_get_windows_storage_path_without_appdata(self):
        """Test Windows storage path falls back when APPDATA is not set."""
        # Save original state
        orig_environ = os.environ.copy()
        
        try:
            os.environ.pop("APPDATA", None)
            
            from codercrucible.parsers.utils import _get_windows_storage_path
            
            # Should use home directory fallback
            path = _get_windows_storage_path()
            
            # Should fall back to .config path
            assert "Cursor" in str(path)
        finally:
            # Restore
            os.environ.clear()
            os.environ.update(orig_environ)

    def test_get_platform_storage_path_macos(self):
        """Test getting platform storage path on macOS."""
        with patch("os.name", "posix"):
            with patch("os.uname") as mock_uname:
                mock_uname.return_value = type('obj', (object,), {'sysname': 'Darwin'})()
                
                from codercrucible.parsers.utils import get_platform_storage_path
                path = get_platform_storage_path()
                
                assert "Library" in str(path)
                assert "Application Support" in str(path)

    def test_get_platform_storage_path_linux(self):
        """Test getting platform storage path on Linux."""
        with patch("os.name", "posix"):
            with patch("os.uname") as mock_uname:
                mock_uname.return_value = type('obj', (object,), {'sysname': 'Linux'})()
                
                from codercrucible.parsers.utils import get_platform_storage_path
                path = get_platform_storage_path()
                
                assert ".config" in str(path)


class TestCursorExportIntegration:
    """End-to-end tests for Cursor export functionality."""

    def test_parse_session_data_to_json(self, tmp_path):
        """Test parsing session data and exporting to JSON."""
        import json
        from codercrucible.parsers.cursor import CursorParser
        
        session_data = {
            "sessionId": "test-session-001",
            "model": "claude-3-5-sonnet",
            "gitBranch": "main",
            "timestamp": 1706000000000,
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": 1706000000000},
                {"role": "assistant", "content": "Hi there!", "timestamp": 1706000001000},
            ]
        }
        
        json_blob = json.dumps(session_data)
        
        parser = CursorParser()
        parsed = parser._parse_session_data("test-session-001", json_blob)
        
        assert parsed is not None
        assert parsed["session_id"] == "test-session-001"
        assert parsed["model"] == "claude-3-5-sonnet"
        assert parsed["git_branch"] == "main"
        assert len(parsed["messages"]) == 2
        assert parsed["stats"]["user_messages"] == 1
        assert parsed["stats"]["assistant_messages"] == 1
        
        # Export to JSONL format (single line JSON)
        output_file = tmp_path / "export.jsonl"
        with open(output_file, "w") as f:
            f.write(json.dumps(parsed) + "\n")
        
        # Verify output
        assert output_file.exists()
        with open(output_file) as f:
            exported = json.loads(f.readline())
            assert exported["session_id"] == "test-session-001"

    def test_parse_session_with_tool_calls(self, tmp_path):
        """Test parsing session with tool calls."""
        import json
        from codercrucible.parsers.cursor import CursorParser
        
        session_data = {
            "sessionId": "test-tools",
            "model": "claude-3-opus",
            "messages": [
                {
                    "role": "user",
                    "content": "Write a file",
                    "timestamp": 1706000000000
                },
                {
                    "role": "assistant",
                    "content": "I'll write that file",
                    "timestamp": 1706000001000,
                    "tool_calls": [
                        {"name": "Write", "input": {"file_path": "test.py", "content": "print('hello')"}}
                    ]
                }
            ]
        }
        
        json_blob = json.dumps(session_data)
        
        parser = CursorParser()
        parsed = parser._parse_session_data("test-tools", json_blob)
        
        assert parsed is not None
        
        # Check tool calls are extracted
        assistant_msg = [m for m in parsed["messages"] if m["role"] == "assistant"][0]
        assert "tool_uses" in assistant_msg
        assert len(assistant_msg["tool_uses"]) == 1
        assert assistant_msg["tool_uses"][0]["tool"] == "Write"
        
        # Check stats
        assert parsed["stats"]["tool_uses"] == 1

    def test_parse_multiple_sessions_to_jsonl(self, tmp_path):
        """Test parsing multiple sessions to JSONL."""
        import json
        from codercrucible.parsers.cursor import CursorParser
        
        sessions = []
        for i in range(3):
            session_data = {
                "sessionId": f"session-{i}",
                "model": "claude-3-sonnet",
                "messages": [{"role": "user", "content": f"Message {i}"}]
            }
            sessions.append(session_data)
        
        parser = CursorParser()
        
        output_file = tmp_path / "export.jsonl"
        with open(output_file, "w") as f:
            for i, session_data in enumerate(sessions):
                json_blob = json.dumps(session_data)
                parsed = parser._parse_session_data(f"session-{i}", json_blob)
                if parsed:
                    f.write(json.dumps(parsed) + "\n")
        
        # Verify all sessions were written
        with open(output_file) as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            # Verify content
            for line in lines:
                data = json.loads(line)
                assert "session_id" in data
                assert "messages" in data
                assert "stats" in data


class TestCursorEdgeCases:
    """Tests for edge cases in Cursor parser."""

    def test_extract_timestamp_seconds_timestamp(self):
        """Test extracting timestamp when value is in seconds (not milliseconds)."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        # Seconds timestamp (less than MILLISECONDS_THRESHOLD)
        data = {"timestamp": 1706000000}
        result = parser._extract_timestamp_from_data(data)
        
        assert result is not None
        assert "T" in result

    def test_extract_timestamp_invalid_numeric(self):
        """Test extracting timestamp with invalid numeric value."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        # Very large invalid timestamp - may raise OverflowError which is caught
        data = {"timestamp": float('inf')}
        result = parser._extract_timestamp_from_data(data)
        
        # Should return None due to OverflowError being caught
        assert result is None

    def test_extract_messages_from_chat_history(self):
        """Test extracting messages from chatHistory field."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        data = {
            "chatHistory": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }
        
        messages = parser._extract_messages(data)
        
        assert len(messages) == 2
        assert messages[0]["role"] == "user"

    def test_extract_messages_from_history(self):
        """Test extracting messages from history field."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        data = {
            "history": [
                {"role": "user", "content": "Test"},
            ]
        }
        
        messages = parser._extract_messages(data)
        
        assert len(messages) == 1

    def test_extract_messages_from_conversations(self):
        """Test extracting messages from conversations field."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        data = {
            "conversations": [
                {"role": "user", "content": "Question?"},
            ]
        }
        
        messages = parser._extract_messages(data)
        
        assert len(messages) == 1

    def test_parse_message_with_list_content(self):
        """Test parsing message with list content (ContentBlock)."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "World!"},
            ]
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert result["content"] == "Hello \nWorld!"

    def test_parse_message_with_tool_use_block(self):
        """Test parsing message with tool_use content block."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll use the tool"},
                {"type": "tool_use", "name": "Read", "input": {}},
            ]
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None

    def test_parse_message_with_reasoning(self):
        """Test parsing message with reasoning field."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": "Let me think",
            "reasoning": "The user is asking about...",
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert "thinking" in result
        assert result["thinking"] == "The user is asking about..."

    def test_parse_message_with_function_tools(self):
        """Test parsing message with function-style tools."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        msg = {
            "role": "assistant",
            "content": "I'll read the file",
            "tools": [
                {"name": "Read", "input": {"file_path": "test.py"}}
            ]
        }
        
        result = parser._parse_message(msg)
        
        assert result is not None
        assert "tool_uses" in result
        assert len(result["tool_uses"]) == 1

    def test_extract_metadata_with_different_timestamp_formats(self):
        """Test metadata extraction with various timestamp formats."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        # Test with start_time field (seconds)
        data = {"start_time": 1706000000}
        metadata = parser._extract_metadata(data)
        assert metadata["start_time"] is not None
        
        # Test with createdAt ISO string
        data = {"createdAt": "2024-01-23T10:00:00Z"}
        metadata = parser._extract_metadata(data)
        assert metadata["start_time"] == "2024-01-23T10:00:00Z"

    def test_extract_metadata_with_end_time(self):
        """Test metadata extraction with end time."""
        from codercrucible.parsers.cursor import CursorParser
        
        parser = CursorParser()
        
        data = {
            "startTime": 1706000000000,
            "lastActiveAt": 1706003600000,
        }
        
        metadata = parser._extract_metadata(data)
        
        assert metadata["start_time"] is not None
        assert metadata["end_time"] is not None
