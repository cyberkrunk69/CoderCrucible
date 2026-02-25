"""Parser for Cursor IDE conversations."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base import BaseParser, ParsedSession, register
from .utils import (
    temp_copy,
    normalise_path,
    extract_timestamp,
    get_platform_storage_path,
    get_workspace_storage_path,
    get_cursor_db_paths,
)

logger = logging.getLogger(__name__)


@register("cursor")
class CursorParser(BaseParser):
    """Parser for Cursor IDE conversation logs.
    
    Cursor stores conversations in SQLite databases:
    - globalStorage/state.vscdb (global sessions)
    - workspaceStorage/*/state.vscdb (workspace-specific sessions)
    
    The cursorDiskKV table contains session data with keys like:
    - composerData:{session_id}
    - bubbleId:{session_id}
    """
    
    # Prefix for session keys in the KV store
    COMPOSER_PREFIX = "composerData:"
    BUBBLE_PREFIX = "bubbleId:"
    
    @property
    def agent_name(self) -> str:
        return "cursor"
    
    def get_storage_paths(self) -> list[str]:
        """Return the storage paths for Cursor."""
        paths = []
        
        global_storage = get_platform_storage_path()
        global_db = global_storage / "state.vscdb"
        if global_db.exists():
            paths.append(str(global_db))
        
        workspace_storage = get_workspace_storage_path()
        if workspace_storage and workspace_storage.exists():
            for workspace_dir in workspace_storage.iterdir():
                if workspace_dir.is_dir():
                    db_path = workspace_dir / "state.vscdb"
                    if db_path.exists():
                        paths.append(str(db_path))
        
        return paths
    
    def discover(self) -> list[dict[str, Any]]:
        """Discover all available Cursor sessions.
        
        Returns:
            List of session metadata dicts with:
            - session_id: Unique identifier
            - timestamp: ISO timestamp when available
            - source_path: Path to the original DB
            - db_key: The KV store key
        """
        sessions = []
        
        # Get all Cursor DB paths
        db_paths = get_cursor_db_paths()
        
        for db_path in db_paths:
            try:
                # Copy to temp location to avoid locks
                temp_path = temp_copy(db_path)
                try:
                    discovered = self._discover_from_db(temp_path, db_path)
                    sessions.extend(discovered)
                finally:
                    # Clean up temp file
                    temp_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to discover sessions from {db_path}: {e}")
        
        # Sort by timestamp (newest first)
        sessions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return sessions
    
    def _discover_from_db(self, db_path: Path, original_path: Path) -> list[dict[str, Any]]:
        """Discover sessions from a single SQLite database.
        
        Args:
            db_path: Path to the (copied) SQLite database
            original_path: Path to the original database (for metadata)
            
        Returns:
            List of session metadata dicts
        """
        sessions = []
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Query the cursorDiskKV table
            cursor.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%' OR key LIKE 'bubbleId:%'")
            
            for row in cursor.fetchall():
                key, value = row
                
                # Extract session ID from key
                if key.startswith(self.COMPOSER_PREFIX):
                    session_id = key[len(self.COMPOSER_PREFIX):]
                elif key.startswith(self.BUBBLE_PREFIX):
                    session_id = key[len(self.BUBBLE_PREFIX):]
                else:
                    continue
                
                # Try to extract timestamp from the JSON value
                timestamp = None
                try:
                    data = json.loads(value)
                    timestamp = self._extract_timestamp_from_data(data)
                except (json.JSONDecodeError, TypeError):
                    pass
                
                sessions.append({
                    "session_id": session_id,
                    "timestamp": timestamp,
                    "source_path": str(original_path),
                    "db_key": key,
                })
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to query cursorDiskKV table: {e}")
        finally:
            conn.close()
        
        return sessions
    
    def _extract_timestamp_from_data(self, data: Any) -> str | None:
        """Extract timestamp from Cursor's session data.
        
        Args:
            data: Parsed JSON data from the session
            
        Returns:
            ISO timestamp string or None
        """
        if not isinstance(data, dict):
            return None
        
        # Try common timestamp fields
        for field in ["timestamp", "createdAt", "created_at", "startTime", "start_time"]:
            value = data.get(field)
            if value:
                if isinstance(value, (int, float)):
                    # Unix timestamp (milliseconds)
                    try:
                        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                        return dt.isoformat()
                    except (ValueError, OSError):
                        pass
                elif isinstance(value, str):
                    # Already ISO string
                    if "T" in value or "-" in value:
                        return value
        
        return None
    
    def parse(self, session_id: str) -> ParsedSession | None:
        """Parse a specific Cursor session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Parsed session dict with standardized schema, or None if parsing fails
        """
        # Search all DBs for this session
        db_paths = get_cursor_db_paths()
        
        for db_path in db_paths:
            try:
                # Copy to temp location to avoid locks
                temp_path = temp_copy(db_path)
                try:
                    result = self._parse_from_db(temp_path, session_id)
                    if result:
                        result["source"] = "cursor"
                        result["source_path"] = str(db_path)
                        return result
                finally:
                    # Clean up temp file
                    temp_path.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to parse session {session_id} from {db_path}: {e}")
        
        logger.warning(f"Session {session_id} not found in any database")
        return None
    
    def _parse_from_db(self, db_path: Path, session_id: str) -> ParsedSession | None:
        """Parse a session from a specific database.
        
        Args:
            db_path: Path to the (copied) SQLite database
            session_id: The session identifier
            
        Returns:
            Parsed session dict or None
        """
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        try:
            # Try both key prefixes
            for prefix in [self.COMPOSER_PREFIX, self.BUBBLE_PREFIX]:
                key = f"{prefix}{session_id}"
                cursor.execute("SELECT value FROM cursorDiskKV WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    return self._parse_session_data(session_id, row[0])
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to query cursorDiskKV table: {e}")
        finally:
            conn.close()
        
        return None
    
    def _parse_session_data(self, session_id: str, json_blob: str) -> ParsedSession | None:
        """Parse session data from JSON blob.
        
        Args:
            session_id: The session identifier
            json_blob: JSON string containing session data
            
        Returns:
            Parsed session dict or None if parsing fails
        """
        try:
            data = json.loads(json_blob)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse session JSON: {e}")
            return None
        
        if not isinstance(data, dict):
            logger.warning(f"Session data is not a dict: {type(data)}")
            return None
        
        # Extract messages
        messages = self._extract_messages(data)
        
        # Extract metadata
        metadata = self._extract_metadata(data)
        
        # Build the parsed session
        session: ParsedSession = {
            "session_id": session_id,
            "model": metadata.get("model"),
            "git_branch": metadata.get("git_branch"),
            "start_time": metadata.get("start_time"),
            "end_time": metadata.get("end_time"),
            "messages": messages,
            "stats": self._compute_stats(messages),
        }
        
        return session
    
    def _extract_messages(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract messages from session data.
        
        Args:
            data: Parsed session JSON
            
        Returns:
            List of message dicts
        """
        messages = []
        
        # Cursor stores messages in various structures
        # Try common locations
        message_lists = []
        
        if "messages" in data:
            message_lists.append(data["messages"])
        if "chatHistory" in data:
            message_lists.append(data["chatHistory"])
        if "history" in data:
            message_lists.append(data["history"])
        if "conversations" in data:
            message_lists.append(data["conversations"])
        
        for msg_list in message_lists:
            if isinstance(msg_list, list):
                for msg in msg_list:
                    parsed = self._parse_message(msg)
                    if parsed:
                        messages.append(parsed)
        
        return messages
    
    def _parse_message(self, msg: Any) -> dict[str, Any] | None:
        """Parse a single message from session data.
        
        Args:
            msg: Message data (dict or other)
            
        Returns:
            Parsed message dict or None
        """
        if not isinstance(msg, dict):
            return None
        
        role = msg.get("role") or msg.get("type")
        
        # Normalize role
        if role in ("user", "human", "prompt"):
            role = "user"
        elif role in ("assistant", "ai", "bot", "cursor"):
            role = "assistant"
        else:
            # Skip unknown roles
            return None
        
        # Extract content
        content = ""
        if "content" in msg:
            content = msg["content"]
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use" or block.get("type") == "tool_use_in_progress":
                            text_parts.append(f"[{block.get('name', 'tool')}]")
                content = "\n".join(text_parts)
        elif "text" in msg:
            content = msg["text"]
        elif "message" in msg:
            # Nested message structure
            nested = msg["message"]
            if isinstance(nested, dict):
                content = nested.get("content", "")
        
        # Skip empty messages
        if not content or (isinstance(content, str) and not content.strip()):
            return None
        
        # Extract thinking
        thinking = None
        if "thinking" in msg:
            thinking = msg["thinking"]
        elif "reasoning" in msg:
            thinking = msg["reasoning"]
        
        # Extract tool uses
        tool_uses = []
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    tool_uses.append({
                        "tool": tc.get("name") or tc.get("function", {}).get("name", "unknown"),
                        "input": str(tc.get("input") or tc.get("function", {}).get("arguments", "")),
                    })
        elif "tools" in msg:
            for tool in msg["tools"]:
                if isinstance(tool, dict):
                    tool_uses.append({
                        "tool": tool.get("name", "unknown"),
                        "input": str(tool.get("input", "")),
                    })
        
        # Extract timestamp
        timestamp = None
        if "timestamp" in msg:
            ts_val = msg["timestamp"]
            if isinstance(ts_val, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ts_val / 1000 if ts_val > 1e10 else ts_val, tz=timezone.utc)
                    timestamp = dt.isoformat()
                except (ValueError, OSError):
                    pass
            elif isinstance(ts_val, str):
                timestamp = ts_val
        elif "createdAt" in msg:
            timestamp = msg["createdAt"]
        
        parsed_msg: dict[str, Any] = {
            "role": role,
            "content": content if isinstance(content, str) else str(content),
        }
        
        if thinking:
            parsed_msg["thinking"] = thinking if isinstance(thinking, str) else str(thinking)
        
        if tool_uses:
            parsed_msg["tool_uses"] = tool_uses
        
        if timestamp:
            parsed_msg["timestamp"] = timestamp
        
        return parsed_msg
    
    def _extract_metadata(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from session data.
        
        Args:
            data: Parsed session JSON
            
        Returns:
            Metadata dict
        """
        metadata = {
            "model": None,
            "git_branch": None,
            "start_time": None,
            "end_time": None,
        }
        
        # Try common model fields
        for field in ["model", "modelId", "model_id", "modelName"]:
            if field in data:
                metadata["model"] = data[field]
                break
        
        # Try git branch
        for field in ["gitBranch", "git_branch", "branch", "currentBranch"]:
            if field in data:
                metadata["git_branch"] = data[field]
                break
        
        # Try timestamps
        for field in ["startTime", "start_time", "createdAt", "timestamp"]:
            if field in data:
                ts_val = data[field]
                if isinstance(ts_val, (int, float)):
                    try:
                        dt = datetime.fromtimestamp(ts_val / 1000 if ts_val > 1e10 else ts_val, tz=timezone.utc)
                        metadata["start_time"] = dt.isoformat()
                        break
                    except (ValueError, OSError):
                        pass
                elif isinstance(ts_val, str):
                    metadata["start_time"] = ts_val
                    break
        
        # Try end time
        for field in ["endTime", "end_time", "lastActiveAt"]:
            if field in data:
                ts_val = data[field]
                if isinstance(ts_val, (int, float)):
                    try:
                        dt = datetime.fromtimestamp(ts_val / 1000 if ts_val > 1e10 else ts_val, tz=timezone.utc)
                        metadata["end_time"] = dt.isoformat()
                        break
                    except (ValueError, OSError):
                        pass
                elif isinstance(ts_val, str):
                    metadata["end_time"] = ts_val
                    break
        
        return metadata
    
    def _compute_stats(self, messages: list[dict[str, Any]]) -> dict[str, int]:
        """Compute statistics for a list of messages.
        
        Args:
            messages: List of parsed messages
            
        Returns:
            Stats dict
        """
        stats = {
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_uses": 0,
        }
        
        for msg in messages:
            role = msg.get("role")
            if role == "user":
                stats["user_messages"] += 1
            elif role == "assistant":
                stats["assistant_messages"] += 1
            
            if "tool_uses" in msg:
                stats["tool_uses"] += len(msg["tool_uses"])
        
        return stats
