"""Pydantic schemas for parsed sessions.

This module defines the unified schema for parsed AI agent sessions,
providing type safety and validation for the parsed data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0"


class ToolCall(BaseModel):
    """A tool call made by the AI agent."""

    tool: str = Field(description="Name of the tool (e.g., 'Read', 'Bash')")
    input: str = Field(description="Summarized input/parameters to the tool")


class Message(BaseModel):
    """A single message in a conversation session."""

    role: str = Field(description="Role: 'user' or 'assistant'")
    content: str = Field(default="", description="Message content text")
    thinking: str | None = Field(
        default=None,
        description="Chain-of-thought reasoning (assistant messages only)"
    )
    tool_uses: list[ToolCall] = Field(
        default_factory=list,
        description="Tool calls made in this message (assistant only)"
    )
    timestamp: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when this message was sent"
    )


class SessionStats(BaseModel):
    """Statistics about a session."""

    user_messages: int = Field(default=0, description="Number of user messages")
    assistant_messages: int = Field(
        default=0, description="Number of assistant messages"
    )
    tool_uses: int = Field(default=0, description="Total tool calls made")
    input_tokens: int = Field(default=0, description="Total input tokens")
    output_tokens: int = Field(default=0, description="Total output tokens")
    skipped_lines: int | None = Field(
        default=None,
        description="Number of malformed JSONL lines skipped"
    )


class SessionMeta(BaseModel):
    """Metadata about a session."""

    session_id: str = Field(description="Unique session identifier")
    project: str | None = Field(
        default=None, description="Project name this session belongs to"
    )
    model: str | None = Field(
        default=None, description="AI model used (e.g., 'claude-opus-4-5')"
    )
    git_branch: str | None = Field(
        default=None, description="Git branch during the session"
    )
    cwd: str | None = Field(
        default=None, description="Working directory at session start"
    )
    claude_version: str | None = Field(
        default=None, description="Claude Code version"
    )


class ParsedSession(BaseModel):
    """A complete parsed session conforming to the unified schema.

    This is the main model for parsed session data that all parsers
    should output. It includes both metadata and the conversation itself.
    """

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="Schema version for future migrations"
    )
    session_id: str = Field(description="Unique session identifier")
    project: str | None = Field(
        default=None, description="Project name this session belongs to"
    )
    model: str | None = Field(
        default=None, description="AI model used"
    )
    git_branch: str | None = Field(
        default=None, description="Git branch during the session"
    )
    start_time: str | None = Field(
        default=None,
        description="Session start timestamp (ISO 8601 format)"
    )
    end_time: str | None = Field(
        default=None,
        description="Session end timestamp (ISO 8601 format)"
    )
    messages: list[Message | dict[str, Any]] = Field(
        default_factory=list,
        description="List of conversation messages"
    )
    stats: SessionStats | dict[str, Any] = Field(
        default_factory=SessionStats,
        description="Session statistics"
    )

    class Config:
        """Pydantic configuration."""

        extra = "allow"


class DiscoveredProject(BaseModel):
    """A discovered project or session directory."""

    id: str = Field(description="Unique identifier (directory name)")
    name: str = Field(description="Human-readable display name")
    path: str = Field(description="Path to the project/session directory")
    session_count: int = Field(
        default=0, description="Number of session files"
    )
    total_size_bytes: int = Field(
        default=0, description="Total size of all session files"
    )
    sessions: list[str] = Field(
        default_factory=list,
        description="List of session IDs (if available during discovery)"
    )
