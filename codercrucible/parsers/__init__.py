"""Parsers for various AI coding agents.

Available parsers:
- cursor: Parser for Cursor IDE conversations
"""

from .base import (
    BaseParser,
    ParserRegistry,
    ParsedSession,
    ParsedMessage,
    create_parser,
    list_available_parsers,
    register,
)
from .utils import (
    temp_copy,
    normalise_path,
    extract_timestamp,
    get_platform_storage_path,
    get_workspace_storage_path,
    get_cursor_db_paths,
)

# Import all registered parsers
from . import cursor  # noqa: F401, E402


def get_parser(name: str, **kwargs) -> BaseParser | None:
    """Get a parser instance by name.
    
    This is an alias for ParserRegistry.create() for convenience.
    
    Args:
        name: The agent name (e.g., "cursor", "claude-code")
        **kwargs: Additional arguments for the parser
        
    Returns:
        Parser instance or None if agent not supported
    """
    return ParserRegistry.create(name, **kwargs)


__all__ = [
    "BaseParser",
    "ParserRegistry",
    "ParsedSession",
    "ParsedMessage",
    "create_parser",
    "list_available_parsers",
    "register",
    "get_parser",
    # Utils
    "temp_copy",
    "normalise_path",
    "extract_timestamp",
    "get_platform_storage_path",
    "get_workspace_storage_path",
    "get_cursor_db_paths",
]
