"""Parser registry and base classes for CoderCrucible.

This module provides the infrastructure for supporting multiple AI coding agents:
- BaseParser: Abstract base class for all parsers
- ParserRegistry: Decorator-based registry for parser implementations
- ParsedSession: TypedDict for standardized session output
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

logger = logging.getLogger(__name__)


# Type alias for parsed messages
ParsedMessage = dict[str, Any]

# Type alias for parsed sessions
ParsedSession = dict[str, Any]


class ParserRegistry:
    """Registry for parser implementations.
    
    Use the @register("agent_name") decorator to register parsers.
    """
    
    _parsers: dict[str, type[BaseParser]] = {}
    
    @classmethod
    def register(cls, name: str) -> Callable[[type[BaseParser]], type[BaseParser]]:
        """Decorator to register a parser.
        
        Args:
            name: The agent name (e.g., "cursor", "claude-code", "cline")
            
        Returns:
            Decorator function that registers the parser class
        """
        def decorator(parser_class: type[BaseParser]) -> type[BaseParser]:
            if name in cls._parsers:
                logger.warning(f"Overwriting existing parser: {name}")
            cls._parsers[name] = parser_class
            logger.info(f"Registered parser: {name}")
            return parser_class
        return decorator
    
    @classmethod
    def get(cls, name: str) -> type[BaseParser] | None:
        """Get a parser class by name.
        
        Args:
            name: The agent name
            
        Returns:
            Parser class or None if not found
        """
        return cls._parsers.get(name)
    
    @classmethod
    def list_parsers(cls) -> list[str]:
        """List all registered parser names.
        
        Returns:
            List of registered parser names
        """
        return list(cls._parsers.keys())
    
    @classmethod
    def create(cls, name: str, **kwargs) -> BaseParser | None:
        """Create a parser instance by name.
        
        Args:
            name: The agent name
            **kwargs: Arguments to pass to the parser constructor
            
        Returns:
            Parser instance or None if not found
        """
        parser_class = cls.get(name)
        if parser_class is None:
            return None
        return parser_class(**kwargs)


# Decorator alias for convenience
register = ParserRegistry.register


class BaseParser(ABC):
    """Abstract base class for all conversation parsers.
    
    Subclasses must implement:
    - discover(): Find all available sessions
    - parse(session_id): Parse a specific session
    
    Optional methods:
    - get_storage_paths(): Return storage paths for this parser
    """
    
    def __init__(self, **kwargs):
        """Initialize the parser.
        
        Args:
            **kwargs: Parser-specific configuration
        """
        self._config = kwargs
    
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the agent name this parser handles."""
        pass
    
    @abstractmethod
    def discover(self) -> list[dict[str, Any]]:
        """Discover all available sessions.
        
        Returns:
            List of session metadata dicts, each containing:
            - session_id: Unique identifier for the session
            - timestamp: ISO timestamp or Unix timestamp
            - source_path: Path to the original storage (for debugging)
            - Any additional metadata the parser can extract
        """
        pass
    
    @abstractmethod
    def parse(self, session_id: str) -> ParsedSession | None:
        """Parse a specific session.
        
        Args:
            session_id: The session identifier (as returned by discover())
            
        Returns:
            Parsed session dict with the standardized schema, or None if parsing fails
        """
        pass
    
    def get_storage_paths(self) -> list[str]:
        """Return the storage paths for this parser.
        
        Returns:
            List of paths where this parser looks for data
        """
        return []
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(agent={self.agent_name})>"


def create_parser(agent_name: str, **kwargs) -> BaseParser | None:
    """Create a parser instance for the specified agent.
    
    Args:
        agent_name: Name of the agent (e.g., "cursor", "claude-code")
        **kwargs: Additional arguments for the parser
        
    Returns:
        Parser instance or None if agent not supported
    """
    return ParserRegistry.create(agent_name, **kwargs)


def list_available_parsers() -> list[str]:
    """List all available parser names.
    
    Returns:
        List of registered parser names
    """
    return ParserRegistry.list_parsers()
