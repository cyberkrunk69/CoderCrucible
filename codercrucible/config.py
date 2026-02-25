"""Persistent config for CoderCrucible — stored at ~/.codercrucible/config.json"""

import json
import os
import sys
from pathlib import Path
from typing import TypedDict

CONFIG_DIR = Path.home() / ".codercrucible"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Cost per enrichment session (Groq llama-3.1-8b-instant is ~$0.001/1K tokens)
# Used as a rough estimate for budget calculations
COST_PER_SESSION = 0.001

# Default model for enrichment (Groq llama-3.1-8b-instant)
DEFAULT_ENRICHMENT_MODEL = "llama-3.1-8b-instant"


class CoderCrucibleConfig(TypedDict, total=False):
    """Expected shape of the config dict."""

    repo: str | None
    excluded_projects: list[str]
    redact_strings: list[str]
    redact_usernames: list[str]
    last_export: dict
    stage: str | None  # "auth" | "configure" | "review" | "confirmed" | "done"
    projects_confirmed: bool  # True once user has addressed folder exclusions
    search: dict | None  # Search config: {"max_content_length": int}
    groq_api_key: str | None  # Groq API key for enrichment


DEFAULT_CONFIG: CoderCrucibleConfig = {
    "repo": None,
    "excluded_projects": [],
    "redact_strings": [],
}


def load_config() -> CoderCrucibleConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                stored = json.load(f)
            return {**DEFAULT_CONFIG, **stored}
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not read {CONFIG_FILE}: {e}", file=sys.stderr)
    return dict(DEFAULT_CONFIG)


def save_config(config: CoderCrucibleConfig) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        print(f"Warning: could not save {CONFIG_FILE}: {e}", file=sys.stderr)


def get_groq_api_key() -> str | None:
    """Get Groq API key from config or GROQ_API_KEY environment variable."""
    config = load_config()
    api_key = config.get("groq_api_key")
    if api_key:
        return api_key
    # Fall back to environment variable
    return os.environ.get("GROQ_API_KEY")


def get_enrichment_model() -> str:
    """Get the default enrichment model from config or ENRICHMENT_MODEL env var.
    
    Priority:
    1. ENRICHMENT_MODEL environment variable
    2. default_enrichment_model in config file
    3. DEFAULT_ENRICHMENT_MODEL constant
    """
    # Check environment variable first (highest priority)
    env_model = os.environ.get("ENRICHMENT_MODEL")
    if env_model:
        return env_model
    
    # Check config file
    config = load_config()
    config_model = config.get("default_enrichment_model")
    if config_model:
        return config_model
    
    # Fall back to default constant
    return DEFAULT_ENRICHMENT_MODEL
