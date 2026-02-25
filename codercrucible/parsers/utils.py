"""Shared utilities for parsers."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def temp_copy(path: Path | str) -> Path:
    """Copy a file to a temporary location and return the new path.
    
    This is useful for working with files that may be locked (like SQLite databases)
    by other processes.
    
    Args:
        path: Path to the file to copy
        
    Returns:
        Path to the temporary copy
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    
    # Create temp file in same directory to avoid cross-device issues
    fd, temp_path = tempfile.mkstemp(suffix=src.suffix, prefix=".codercrucible_")
    os.close(fd)
    
    shutil.copy2(src, temp_path)
    return Path(temp_path)


def normalise_path(path: Path | str, project_root: Path | str | None = None) -> str:
    """Replace home directory with ~, optionally make relative to project_root.
    
    Args:
        path: Path to normalise
        project_root: Optional root to make path relative to
        
    Returns:
        Normalized path string
    """
    path = Path(path)
    
    # Expand user home
    expanded = path.expanduser()
    
    # Replace home with ~
    try:
        home = Path.home()
        if expanded.is_relative_to(home):
            try:
                rel = expanded.relative_to(home)
                return f"~/{rel}"
            except ValueError:
                pass
    except (OSError, ValueError):
        pass
    
    # If project_root provided, try to make relative
    if project_root:
        project_root = Path(project_root).expanduser()
        try:
            if expanded.is_relative_to(project_root):
                rel = expanded.relative_to(project_root)
                return str(rel)
        except ValueError:
            pass
    
    return str(expanded)


def extract_timestamp(iso_string: str | None) -> float | None:
    """Convert ISO format timestamp string to Unix timestamp.
    
    Args:
        iso_string: ISO format timestamp string (e.g., "2025-01-15T10:00:00+00:00")
        
    Returns:
        Unix timestamp (seconds since epoch), or None if conversion fails
    """
    if not iso_string:
        return None
    
    try:
        # Handle various ISO formats
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, AttributeError):
        return None


def get_platform_storage_path() -> Path:
    """Get the platform-agnostic path to Cursor's global storage.
    
    Returns:
        Path to Cursor's globalStorage directory
    """
    home = Path.home()
    
    if os.name == "posix":
        if os.uname().sysname == "Darwin":
            # macOS
            return home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage"
        else:
            # Linux
            return home / ".config" / "Cursor" / "User" / "globalStorage"
    elif os.name == "nt":
        # Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Cursor" / "User" / "globalStorage"
    
    # Fallback to Linux path
    return home / ".config" / "Cursor" / "User" / "globalStorage"


def get_workspace_storage_path() -> Path | None:
    """Get the platform-agnostic path to Cursor's workspace storage.
    
    Returns:
        Path to Cursor's workspaceStorage directory, or None if not found
    """
    global_storage = get_platform_storage_path()
    workspace_storage = global_storage.parent / "workspaceStorage"
    
    if workspace_storage.exists():
        return workspace_storage
    
    # Check alternative location on Linux
    if os.name == "posix" and os.uname().sysname != "Darwin":
        alt = Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage"
        if alt.exists():
            return alt
    
    return None


def get_cursor_db_paths() -> list[Path]:
    """Get all Cursor SQLite database paths.
    
    Returns:
        List of paths to Cursor's state.vscdb files
    """
    paths = []
    
    # Global storage DB
    global_storage = get_platform_storage_path()
    global_db = global_storage / "state.vscdb"
    if global_db.exists():
        paths.append(global_db)
    
    # Workspace storage DBs
    workspace_storage = get_workspace_storage_path()
    if workspace_storage and workspace_storage.exists():
        for workspace_dir in workspace_storage.iterdir():
            if workspace_dir.is_dir():
                db_path = workspace_dir / "state.vscdb"
                if db_path.exists():
                    paths.append(db_path)
    
    return paths
