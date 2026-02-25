"""Tests for codercrucible CLI enrichment (think-cheap command)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codercrucible.cli import _handle_think_cheap


class TestThinkCheapCommand:
    """Tests for the think-cheap CLI command."""

    def test_missing_api_key(self, tmp_path, capsys):
        """Test that command fails without API key."""
        # Create temporary input file
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"id": "1", "text": "test"}\n')

        output_file = tmp_path / "output.jsonl"

        with patch("codercrucible.cli.get_groq_api_key", return_value=None):
            with pytest.raises(SystemExit):
                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                )

        captured = capsys.readouterr()
        assert "API key" in captured.out or "error" in captured.out

    def test_missing_input_file(self, capsys):
        """Test that command fails when input file doesn't exist."""
        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with pytest.raises(SystemExit):
                _create_args_and_call(
                    input_file="/nonexistent/file.jsonl",
                    output_file="/tmp/output.jsonl",
                )

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "error" in captured.out

    def test_empty_input_file(self, tmp_path, capsys):
        """Test that command fails with empty input file."""
        input_file = tmp_path / "empty.jsonl"
        input_file.write_text("")

        output_file = tmp_path / "output.jsonl"

        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with pytest.raises(SystemExit):
                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                )

        captured = capsys.readouterr()
        assert "no sessions" in captured.out.lower() or "error" in captured.out

    def test_invalid_json_in_input(self, tmp_path, capsys):
        """Test that command fails with invalid JSON in input."""
        input_file = tmp_path / "invalid.jsonl"
        input_file.write_text('{"id": "1", "text": "test"}\ninvalid json\n')

        output_file = tmp_path / "output.jsonl"

        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with pytest.raises(SystemExit):
                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                )

        captured = capsys.readouterr()
        assert "json" in captured.out.lower() or "error" in captured.out

    def test_successful_enrichment(self, tmp_path, monkeypatch):
        """Test successful enrichment workflow."""
        # Create input file
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"id": "1", "text": "Hello, I need help with a bug"}\n')

        output_file = tmp_path / "output.jsonl"

        # Mock the EnrichmentOrchestrator
        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with patch("codercrucible.cli.asyncio.run") as mock_asyncio_run:
                # Mock the enrich_sessions result
                enriched_result = [
                    {
                        "id": "1",
                        "text": "Hello, I need help with a bug",
                        "enrichments": {
                            "emotional": {"emotional_tags": ["frustration"], "confidence": 0.9}
                        }
                    }
                ]
                mock_asyncio_run.return_value = enriched_result

                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                    dimensions="emotional",
                )

        # Verify output was written
        assert output_file.exists()
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 1
        result = json.loads(lines[0])
        assert "enrichments" in result

    def test_limit_sessions(self, tmp_path, monkeypatch):
        """Test that --limit parameter works correctly."""
        # Create input with multiple sessions
        input_file = tmp_path / "input.jsonl"
        sessions = [{"id": str(i), "text": f"Session {i}"} for i in range(5)]
        input_file.write_text("\n".join(json.dumps(s) for s in sessions) + "\n")

        output_file = tmp_path / "output.jsonl"

        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with patch("codercrucible.cli.asyncio.run") as mock_asyncio_run:
                # Return all sessions
                mock_asyncio_run.return_value = sessions[:2]

                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                    limit=2,
                )

                # Verify the asyncio.run was called
                assert mock_asyncio_run.called

    def test_default_dimensions(self, tmp_path):
        """Test that default dimensions are used correctly."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('{"id": "1", "text": "test"}\n')

        output_file = tmp_path / "output.jsonl"

        with patch("codercrucible.cli.get_groq_api_key", return_value="test-key"):
            with patch("codercrucible.cli.asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.return_value = []

                _create_args_and_call(
                    input_file=str(input_file),
                    output_file=str(output_file),
                )

                # Verify asyncio.run was called (meaning it tried to enrich)
                assert mock_asyncio_run.called


class TestThinkCheapArgParsing:
    """Tests for think-cheap argument parsing."""

    def test_dimensions_argument_required(self):
        """Test that --input and --output are required."""
        from codercrucible.cli import main
        import sys

        # Test missing required arguments
        with patch("sys.argv", ["codercrucible", "think-cheap"]):
            with pytest.raises(SystemExit):
                main()


def _create_args_and_call(
    input_file: str,
    output_file: str,
    dimensions: str = "intent,emotional,security",
    limit: int = 0,
    budget: float = 0.50,
    model: str = "llama-3.1-8b-instant",
):
    """Helper to create mock args and call the handler."""
    # Create a mock args object
    args = MagicMock()
    args.input = input_file
    args.output = output_file
    args.dimensions = dimensions
    args.limit = limit
    args.budget = budget
    args.model = model

    _handle_think_cheap(args)
