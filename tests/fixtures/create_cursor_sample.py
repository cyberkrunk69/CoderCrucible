#!/usr/bin/env python3
"""Create a sample Cursor SQLite database for testing."""

import json
import sqlite3
import sys
from pathlib import Path

# Sample session data representing typical Cursor conversations
SESSIONS = [
    {
        "key": "composerData:session-001",
        "value": json.dumps({
            "sessionId": "session-001",
            "model": "claude-3-5-sonnet-20241022",
            "gitBranch": "main",
            "timestamp": 1706000000000,
            "messages": [
                {
                    "role": "user",
                    "content": "Write a hello world program in Python",
                    "timestamp": 1706000000000
                },
                {
                    "role": "assistant",
                    "content": "Here's a hello world program:",
                    "timestamp": 1706000001000,
                    "tool_calls": [
                        {
                            "name": "Write",
                            "input": {
                                "file_path": "main.py",
                                "content": "print('Hello, World!')\n"
                            }
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": "Can you add a function?",
                    "timestamp": 1706000002000
                },
                {
                    "role": "assistant",
                    "content": "I'll add a greet function:",
                    "timestamp": 1706000003000,
                    "tool_calls": [
                        {
                            "name": "Edit",
                            "input": {
                                "file_path": "main.py",
                                "content": "def greet(name):\n    return f'Hello, {name}!'\n\nif __name__ == '__main__':\n    print(greet('World'))\n"
                            }
                        }
                    ]
                }
            ]
        })
    },
    {
        "key": "composerData:session-002", 
        "value": json.dumps({
            "sessionId": "session-002",
            "model": "claude-3-opus-20240229",
            "gitBranch": "feature/new-api",
            "timestamp": 1706500000000,
            "messages": [
                {
                    "role": "user",
                    "content": "Explain what a decorator is in Python",
                    "timestamp": 1706500000000
                },
                {
                    "role": "assistant",
                    "content": "A decorator in Python is...",
                    "timestamp": 1706500001000,
                    "thinking": "The user is asking about Python decorators. I should explain the concept clearly."
                }
            ]
        })
    },
    {
        "key": "bubbleId:bubble-session-001",
        "value": json.dumps({
            "sessionId": "bubble-session-001",
            "model": "claude-3-haiku-20240307",
            "createdAt": "2024-01-20T15:30:00Z",
            "messages": [
                {
                    "role": "user",
                    "content": "Quick question about git rebase",
                    "timestamp": 1705771800000
                },
                {
                    "role": "assistant", 
                    "content": "Git rebase is used to...",
                    "timestamp": 1705771805000
                }
            ]
        })
    }
]


def create_sample_db(output_path: Path):
    """Create a sample Cursor SQLite database."""
    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()
    
    # Create the cursorDiskKV table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursorDiskKV (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Insert sample sessions
    for session in SESSIONS:
        cursor.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (session["key"], session["value"])
        )
    
    conn.commit()
    conn.close()
    print(f"Created sample database at {output_path}")
    print(f"Inserted {len(SESSIONS)} sessions")


if __name__ == "__main__":
    output_path = Path(__file__).parent / "cursor_sample.db"
    create_sample_db(output_path)
