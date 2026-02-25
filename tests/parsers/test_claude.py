"""Tests for the Claude Code parser."""

import json

import pytest

from codercrucible.parsers import create_parser
from codercrucible.parsers.claude import (
    AnonymizerWrapper,
    ClaudeParser,
    _build_project_name,
    _extract_assistant_content,
    _extract_user_content,
    _normalize_timestamp,
    _parse_session_file,
    _process_entry,
    _summarize_tool_input,
)


@pytest.fixture
def mock_anonymizer():
    """AnonymizerWrapper with test username for deterministic testing."""
    return AnonymizerWrapper(extra_usernames=["testuser"])


@pytest.fixture
def sample_user_entry():
    """Sample user entry dict."""
    return {
        "type": "user",
        "timestamp": 1706000000000,
        "cwd": "/Users/testuser/Documents/myproject",
        "gitBranch": "main",
        "version": "1.0.0",
        "sessionId": "abc-123",
        "message": {
            "content": "Fix the login bug in src/auth.py",
        },
    }


@pytest.fixture
def sample_assistant_entry():
    """Sample assistant entry dict."""
    return {
        "type": "assistant",
        "timestamp": 1706000001000,
        "message": {
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "thinking", "thinking": "Let me look at the auth file."},
                {"type": "text", "text": "I'll fix the login bug."},
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": "/Users/testuser/Documents/myproject/src/auth.py"},
                },
            ],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 100,
                "cache_read_input_tokens": 200,
            },
        },
    }


class TestClaudeParser:
    """Tests for ClaudeParser class."""

    def test_parser_creation(self):
        """Test that parser can be created."""
        parser = ClaudeParser()
        assert parser is not None
        assert parser.agent_name == "claude"

    def test_parser_with_custom_dir(self, tmp_path):
        """Test parser with custom Claude directory."""
        parser = ClaudeParser(claude_dir=tmp_path)
        assert parser.claude_dir == tmp_path

    def test_discover_with_no_projects(self, tmp_path):
        """Test discover returns empty list when no projects exist."""
        parser = ClaudeParser(claude_dir=tmp_path)
        result = parser.discover()
        assert result == []

    def test_discover_finds_projects(self, tmp_path):
        """Test discover finds projects with sessions."""
        projects_dir = tmp_path / "projects"
        proj = projects_dir / "-Users-testuser-Documents-myapp"
        proj.mkdir(parents=True)

        session = proj / "session1.jsonl"
        session.write_text(
            '{"type":"user","timestamp":1706000000000,"message":{"content":"Hi"},"cwd":"/tmp"}\n'
            '{"type":"assistant","timestamp":1706000001000,"message":{"model":"m","content":[{"type":"text","text":"Hey"}],"usage":{"input_tokens":1,"output_tokens":1}}}\n'
        )

        parser = ClaudeParser(claude_dir=tmp_path)
        discovered = parser.discover()

        assert len(discovered) == 1
        assert discovered[0]["name"] == "myapp"
        assert discovered[0]["session_count"] == 1

    def test_parse_project(self, tmp_path, mock_anonymizer):
        """Test parsing all sessions in a project."""
        projects_dir = tmp_path / "projects"
        proj = projects_dir / "test-project"
        proj.mkdir(parents=True)

        session = proj / "session1.jsonl"
        session.write_text(
            '{"type":"user","timestamp":1706000000000,"message":{"content":"Hello"},"cwd":"/tmp"}\n'
            '{"type":"assistant","timestamp":1706000001000,"message":{"model":"m","content":[{"type":"text","text":"Hi"}],"usage":{"input_tokens":1,"output_tokens":1}}}\n'
        )

        parser = ClaudeParser(claude_dir=tmp_path)
        sessions = parser.parse_project("test-project", anonymizer=mock_anonymizer)

        assert len(sessions) == 1
        assert sessions[0]["project"] == "test-project"

    def test_parse_session_not_found(self, tmp_path, mock_anonymizer):
        """Test parsing a nonexistent session raises error."""
        parser = ClaudeParser(claude_dir=tmp_path)

        with pytest.raises(FileNotFoundError):
            parser.parse("nonexistent-session", anonymizer=mock_anonymizer)


class TestBuildProjectName:
    """Tests for _build_project_name function."""

    def test_documents_prefix(self):
        assert _build_project_name("-Users-alice-Documents-myproject") == "myproject"

    def test_home_prefix(self):
        assert _build_project_name("-home-bob-project") == "project"

    def test_standalone(self):
        assert _build_project_name("standalone") == "standalone"


class TestNormalizeTimestamp:
    """Tests for _normalize_timestamp function."""

    def test_none(self):
        assert _normalize_timestamp(None) is None

    def test_string_passthrough(self):
        ts = "2025-01-15T10:00:00+00:00"
        assert _normalize_timestamp(ts) == ts

    def test_int_ms_to_iso(self):
        result = _normalize_timestamp(1706000000000)
        assert result is not None
        assert "2024" in result
        assert "T" in result


class TestSummarizeToolInput:
    """Tests for _summarize_tool_input function."""

    def test_read_tool(self, mock_anonymizer):
        result = _summarize_tool_input(
            "Read", {"file_path": "/tmp/test.py"}, mock_anonymizer
        )
        assert "test.py" in result

    def test_write_tool(self, mock_anonymizer):
        result = _summarize_tool_input(
            "Write", {"file_path": "/tmp/test.py", "content": "abc"}, mock_anonymizer
        )
        assert "test.py" in result
        assert "3 chars" in result

    def test_bash_tool(self, mock_anonymizer):
        result = _summarize_tool_input(
            "Bash", {"command": "ls -la"}, mock_anonymizer
        )
        assert "ls -la" in result


class TestExtractUserContent:
    """Tests for _extract_user_content function."""

    def test_string_content(self, mock_anonymizer):
        entry = {"message": {"content": "Fix the bug"}}
        result = _extract_user_content(entry, mock_anonymizer)
        assert result == "Fix the bug"

    def test_list_content(self, mock_anonymizer):
        entry = {
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ]
            }
        }
        result = _extract_user_content(entry, mock_anonymizer)
        assert "Hello" in result
        assert "World" in result

    def test_empty_content(self, mock_anonymizer):
        entry = {"message": {"content": ""}}
        assert _extract_user_content(entry, mock_anonymizer) is None


class TestExtractAssistantContent:
    """Tests for _extract_assistant_content function."""

    def test_text_blocks(self, mock_anonymizer):
        entry = {
            "message": {
                "content": [
                    {"type": "text", "text": "Here's the fix."},
                ]
            }
        }
        result = _extract_assistant_content(entry, mock_anonymizer, include_thinking=True)
        assert result is not None
        assert result["content"] == "Here's the fix."

    def test_thinking_included(self, mock_anonymizer):
        entry = {
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                    {"type": "text", "text": "Done."},
                ]
            }
        }
        result = _extract_assistant_content(entry, mock_anonymizer, include_thinking=True)
        assert "thinking" in result
        assert "Let me think..." in result["thinking"]

    def test_thinking_excluded(self, mock_anonymizer):
        entry = {
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                    {"type": "text", "text": "Done."},
                ]
            }
        }
        result = _extract_assistant_content(entry, mock_anonymizer, include_thinking=False)
        assert "thinking" not in result

    def test_tool_uses(self, mock_anonymizer):
        entry = {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/tmp/test.py"},
                    },
                ]
            }
        }
        result = _extract_assistant_content(entry, mock_anonymizer, include_thinking=True)
        assert result is not None
        assert len(result["tool_uses"]) == 1
        assert result["tool_uses"][0]["tool"] == "Read"


class TestProcessEntry:
    """Tests for _process_entry function."""

    def test_user_entry(self, mock_anonymizer, sample_user_entry):
        messages = []
        metadata = {
            "session_id": "test",
            "cwd": None,
            "git_branch": None,
            "claude_version": None,
            "model": None,
            "start_time": None,
            "end_time": None,
        }
        stats = {
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_uses": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        _process_entry(
            sample_user_entry, messages, metadata, stats, mock_anonymizer, True
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert stats["user_messages"] == 1
        assert metadata["git_branch"] == "main"

    def test_assistant_entry(self, mock_anonymizer, sample_assistant_entry):
        messages = []
        metadata = {
            "session_id": "test",
            "cwd": None,
            "git_branch": None,
            "claude_version": None,
            "model": None,
            "start_time": None,
            "end_time": None,
        }
        stats = {
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_uses": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        _process_entry(
            sample_assistant_entry, messages, metadata, stats, mock_anonymizer, True
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert stats["assistant_messages"] == 1
        assert stats["input_tokens"] > 0


class TestParseSessionFile:
    """Tests for _parse_session_file function."""

    def test_valid_jsonl(self, tmp_path, mock_anonymizer):
        f = tmp_path / "session.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": 1706000000000,
                "message": {"content": "Hello"},
                "cwd": "/tmp/proj",
            },
            {
                "type": "assistant",
                "timestamp": 1706000001000,
                "message": {
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = _parse_session_file(f, mock_anonymizer)
        assert result is not None
        assert len(result["messages"]) == 2
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_malformed_lines_skipped(self, tmp_path, mock_anonymizer):
        f = tmp_path / "session.jsonl"
        f.write_text(
            '{"type":"user","timestamp":1706000000000,"message":{"content":"Hello"},"cwd":"/tmp"}\n'
            "not valid json\n"
            '{"type":"assistant","timestamp":1706000001000,"message":{"model":"m","content":[{"type":"text","text":"Hi"}],"usage":{"input_tokens":1,"output_tokens":1}}}\n'
        )
        result = _parse_session_file(f, mock_anonymizer)
        assert result is not None
        assert len(result["messages"]) == 2

    def test_empty_file(self, tmp_path, mock_anonymizer):
        f = tmp_path / "session.jsonl"
        f.write_text("")
        result = _parse_session_file(f, mock_anonymizer)
        assert result is None


class TestParserRegistryIntegration:
    """Tests for using ClaudeParser through the registry."""

    def test_create_via_registry(self):
        """Test creating ClaudeParser through create_parser."""
        parser = create_parser("claude")
        assert parser is not None
        assert isinstance(parser, ClaudeParser)
        assert parser.agent_name == "claude"

    def test_discover_via_registry(self, tmp_path):
        """Test discover through registry-created parser."""
        projects_dir = tmp_path / "projects"
        proj = projects_dir / "test-proj"
        proj.mkdir(parents=True)

        session = proj / "s1.jsonl"
        session.write_text(
            '{"type":"user","timestamp":1706000000000,"message":{"content":"Hi"},"cwd":"/tmp"}\n'
        )

        parser = create_parser("claude", claude_dir=tmp_path)
        discovered = parser.discover()

        assert len(discovered) == 1
        assert discovered[0]["name"] == "test-proj"
