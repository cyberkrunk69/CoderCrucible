"""Tests for config getter functions in codercrucible.config.

These tests cover:
- get_enrichment_model() priority chain (env > config > default)
- get_groq_api_key() priority chain (env > config)
- Configuration loading and saving edge cases
"""

import json
import os

import pytest

from codercrucible.config import (
    DEFAULT_ENRICHMENT_MODEL,
    get_enrichment_model,
    get_groq_api_key,
    load_config,
    save_config,
)


class TestGetEnrichmentModel:
    """Tests for get_enrichment_model() priority chain."""

    def test_env_var_takes_priority(self, tmp_config, monkeypatch):
        """When ENRICHMENT_MODEL env var is set, it should be returned."""
        monkeypatch.setenv("ENRICHMENT_MODEL", "custom-model-from-env")
        config = load_config()
        config["default_enrichment_model"] = "model-from-config"
        save_config(config)

        result = get_enrichment_model()

        assert result == "custom-model-from-env"

    def test_config_takes_priority_over_default(
        self, tmp_config, monkeypatch
    ):
        """When env var not set but config has value, config value is used."""
        monkeypatch.delenv("ENRICHMENT_MODEL", raising=False)
        config = load_config()
        config["default_enrichment_model"] = "model-from-config"
        save_config(config)

        result = get_enrichment_model()

        assert result == "model-from-config"

    def test_default_used_when_nothing_set(self, tmp_config, monkeypatch):
        """When neither env nor config has value, DEFAULT_ENRICHMENT_MODEL is used."""
        monkeypatch.delenv("ENRICHMENT_MODEL", raising=False)
        config = load_config()
        if "default_enrichment_model" in config:
            del config["default_enrichment_model"]
        save_config(config)

        result = get_enrichment_model()

        assert result == DEFAULT_ENRICHMENT_MODEL

    def test_empty_env_var_treated_as_not_set(self, tmp_config, monkeypatch):
        """Empty string in ENRICHMENT_MODEL env var should be treated as not set."""
        monkeypatch.setenv("ENRICHMENT_MODEL", "")
        config = load_config()
        config["default_enrichment_model"] = "model-from-config"
        save_config(config)

        result = get_enrichment_model()

        assert result == "model-from-config"

    def test_empty_config_value_treated_as_not_set(self, tmp_config, monkeypatch):
        """Empty string in config should be treated as not set."""
        monkeypatch.delenv("ENRICHMENT_MODEL", raising=False)
        config = load_config()
        config["default_enrichment_model"] = ""
        save_config(config)

        result = get_enrichment_model()

        assert result == DEFAULT_ENRICHMENT_MODEL


class TestGetGroqApiKey:
    """Tests for get_groq_api_key() priority chain.

    Note: get_groq_api_key() prioritizes config over environment variable:
    1. config file value (if set)
    2. GROQ_API_KEY environment variable
    """

    def test_config_takes_priority_over_env(self, tmp_config, monkeypatch):
        """When config has groq_api_key, it should be returned over env var."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk_env-key123")
        config = load_config()
        config["groq_api_key"] = "gsk_config-key456"
        save_config(config)

        result = get_groq_api_key()

        assert result == "gsk_config-key456"

    def test_env_used_when_config_not_set(self, tmp_config, monkeypatch):
        """When config doesn't have value but env var is set, env var is used."""
        config = load_config()
        if "groq_api_key" in config:
            del config["groq_api_key"]
        save_config(config)
        monkeypatch.setenv("GROQ_API_KEY", "gsk_env-key123")

        result = get_groq_api_key()

        assert result == "gsk_env-key123"

    def test_none_returned_when_nothing_set(self, tmp_config, monkeypatch):
        """When neither env nor config has value, None is returned."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        config = load_config()
        if "groq_api_key" in config:
            del config["groq_api_key"]
        save_config(config)

        result = get_groq_api_key()

        assert result is None

    def test_empty_string_in_config_returns_none(self, tmp_config, monkeypatch):
        """Empty string in config groq_api_key should return None."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        config = load_config()
        config["groq_api_key"] = ""
        save_config(config)

        result = get_groq_api_key()

        assert result is None


class TestConfigIo:
    """Additional tests for config loading and saving edge cases."""

    def test_save_and_load_returns_same_data(self, tmp_config):
        """Saving and then loading returns the same data."""
        test_config = {
            "repo": "test/repo",
            "excluded_projects": ["node_modules", ".git"],
            "redact_strings": ["secret1", "secret2"],
            "redact_usernames": True,
            "default_enrichment_model": "llama-3.1-8b-instant",
            "groq_api_key": "gsk_test-key",
        }
        save_config(test_config)
        loaded = load_config()

        assert loaded["repo"] == test_config["repo"]
        assert loaded["excluded_projects"] == test_config["excluded_projects"]
        assert loaded["redact_strings"] == test_config["redact_strings"]
        assert loaded["default_enrichment_model"] == test_config["default_enrichment_model"]
        assert loaded["groq_api_key"] == test_config["groq_api_key"]

    def test_config_directory_created_if_not_exists(self, tmp_config):
        """save_config() creates the config directory if it doesn't exist."""
        # Ensure the directory doesn't exist
        assert not tmp_config.parent.exists()
        save_config({"repo": "test/repo"})
        assert tmp_config.parent.exists()
        assert tmp_config.exists()

    def test_load_config_missing_file_returns_defaults(self, tmp_config):
        """load_config() handles missing config file gracefully."""
        # Ensure no config file exists
        assert not tmp_config.exists()
        config = load_config()

        assert config["repo"] is None
        assert config["excluded_projects"] == []
        assert config["redact_strings"] == []

    def test_load_config_with_only_enrichment_model(self, tmp_config):
        """Config file with only enrichment model is loaded correctly."""
        tmp_config.parent.mkdir(parents=True, exist_ok=True)
        tmp_config.write_text(json.dumps({"default_enrichment_model": "custom-model"}))
        config = load_config()

        assert config["default_enrichment_model"] == "custom-model"
        # Defaults still present
        assert config["repo"] is None
