"""
Tests for the enrichment module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from codercrucible.enrichment import (
    IntentType,
    EmotionalEnrichment,
    SecurityEnrichment,
    IntentEnrichment,
    EnrichmentOrchestrator,
    get_enrichment_prompt,
    DIMENSION_PROMPTS,
)


def test_intent_type_enum():
    """Test IntentType enum values."""
    assert IntentType.DEBUG.value == "debug"
    assert IntentType.FEATURE.value == "feature"
    assert IntentType.QUESTION.value == "question"
    assert IntentType.VENT.value == "vent"
    assert IntentType.EXPLORATION.value == "exploration"
    assert IntentType.OTHER.value == "other"


def test_emotional_enrichment_model():
    """Test EmotionalEnrichment Pydantic model."""
    enrichment = EmotionalEnrichment(
        emotional_tags=["frustration", "confusion"],
        confidence=0.85,
    )
    assert enrichment.emotional_tags == ["frustration", "confusion"]
    assert enrichment.confidence == 0.85


def test_security_enrichment_model():
    """Test SecurityEnrichment Pydantic model."""
    enrichment = SecurityEnrichment(
        security_issues=["hardcoded API key"],
        confidence=0.92,
        excerpts=["api_key = 'sk-1234567890'"],
    )
    assert len(enrichment.security_issues) == 1
    assert enrichment.confidence == 0.92
    assert enrichment.excerpts is not None


def test_intent_enrichment_model():
    """Test IntentEnrichment Pydantic model."""
    enrichment = IntentEnrichment(
        intent=IntentType.DEBUG,
        confidence=0.78,
    )
    assert enrichment.intent == IntentType.DEBUG
    assert enrichment.confidence == 0.78


def test_get_enrichment_prompt():
    """Test getting prompt templates."""
    assert get_enrichment_prompt("emotional") == DIMENSION_PROMPTS["emotional"]
    assert get_enrichment_prompt("security") == DIMENSION_PROMPTS["security"]
    assert get_enrichment_prompt("intent") == DIMENSION_PROMPTS["intent"]
    assert get_enrichment_prompt("unknown") == ""


def test_dimension_prompts():
    """Test that all dimension prompts are defined."""
    assert "emotional" in DIMENSION_PROMPTS
    assert "security" in DIMENSION_PROMPTS
    assert "intent" in DIMENSION_PROMPTS
    assert "{text}" in DIMENSION_PROMPTS["emotional"]
    assert "{text}" in DIMENSION_PROMPTS["security"]
    assert "{text}" in DIMENSION_PROMPTS["intent"]


@pytest.mark.asyncio
async def test_orchestrator_init():
    """Test EnrichmentOrchestrator initialization."""
    mock_llm = AsyncMock()
    orchestrator = EnrichmentOrchestrator(
        llm_call=mock_llm,
        batch_size=5,
        max_concurrent=3,
        audit_logging=False,
    )
    assert orchestrator.llm_call == mock_llm
    assert orchestrator.batch_size == 5
    assert orchestrator.max_concurrent == 3
    assert orchestrator.audit_logging is False


@pytest.mark.asyncio
async def test_orchestrator_init_with_audit():
    """Test EnrichmentOrchestrator with audit logging enabled."""
    mock_llm = AsyncMock()
    orchestrator = EnrichmentOrchestrator(
        llm_call=mock_llm,
        audit_logging=True,
    )
    assert orchestrator.audit_logging is True


@pytest.mark.asyncio
async def test_enrich_sessions_empty():
    """Test enrich_sessions with empty input."""
    mock_llm = AsyncMock()
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_sessions([], ["emotional"])
    assert result == []

    result = await orchestrator.enrich_sessions([{"id": "1", "text": "test"}], [])
    assert result == [{"id": "1", "text": "test", "enrichments": {}}]


@pytest.mark.asyncio
async def test_enrich_sessions_returns_enriched():
    """Test that enrich_sessions returns sessions with enrichments."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["frustration"], "confidence": 0.9}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    sessions = [
        {"id": "1", "text": "Hello, I need help fixing a bug"},
        {"id": "2", "text": "Can you add a new feature?"},
    ]

    enriched = await orchestrator.enrich_sessions(
        sessions,
        dimensions=["emotional"],
    )

    assert len(enriched) == 2
    assert "enrichments" in enriched[0]
    assert enriched[0]["id"] == "1"
    assert enriched[1]["id"] == "2"


@pytest.mark.asyncio
async def test_enrich_sessions_multiple_dimensions():
    """Test enrich_sessions with multiple dimensions."""
    mock_response = MagicMock()
    mock_response.content = '{"intent": "debug", "confidence": 0.88}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    sessions = [{"id": "1", "text": "There's a bug in my code"}]

    enriched = await orchestrator.enrich_sessions(
        sessions,
        dimensions=["emotional", "intent"],
    )

    assert len(enriched) == 1
    assert "emotional" in enriched[0]["enrichments"]
    assert "intent" in enriched[0]["enrichments"]


@pytest.mark.asyncio
async def test_enrich_single_emotional():
    """Test single text enrichment for emotional dimension."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["frustration"], "confidence": 0.9}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_single(
        "This is so frustrating, nothing works!",
        dimensions=["emotional"],
    )

    assert "emotional" in result
    assert isinstance(result["emotional"], EmotionalEnrichment)
    assert "frustration" in result["emotional"].emotional_tags


@pytest.mark.asyncio
async def test_enrich_single_security():
    """Test single text enrichment for security dimension."""
    mock_response = MagicMock()
    mock_response.content = '{"security_issues": ["hardcoded token"], "confidence": 0.95, "excerpts": ["token = \\"abc123\\""]}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_single(
        "Here's my code: token = 'abc123'",
        dimensions=["security"],
    )

    assert "security" in result
    assert isinstance(result["security"], SecurityEnrichment)
    assert len(result["security"].security_issues) > 0


@pytest.mark.asyncio
async def test_enrich_single_intent():
    """Test single text enrichment for intent dimension."""
    mock_response = MagicMock()
    mock_response.content = '{"intent": "debug", "confidence": 0.88}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_single(
        "There's a bug in my code",
        dimensions=["intent"],
    )

    assert "intent" in result
    assert isinstance(result["intent"], IntentEnrichment)
    assert result["intent"].intent == IntentType.DEBUG


@pytest.mark.asyncio
async def test_enrich_single_multiple_dimensions():
    """Test single text enrichment with multiple dimensions."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["curiosity"], "confidence": 0.8}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_single(
        "How does this work?",
        dimensions=["emotional", "intent"],
    )

    assert "emotional" in result
    assert "intent" in result


@pytest.mark.asyncio
async def test_enrich_single_with_session_id():
    """Test single text enrichment with custom session ID."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["neutral"], "confidence": 0.5}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    result = await orchestrator.enrich_single(
        "Hello world",
        dimensions=["emotional"],
        session_id="custom-session-123",
    )

    assert "emotional" in result
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_sessions_preserves_other_fields():
    """Test that enrich_sessions preserves other session fields."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["neutral"], "confidence": 0.5}'
    mock_response.cost_usd = 0.001
    mock_response.input_tokens = 100
    mock_response.output_tokens = 50
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    sessions = [
        {"id": "1", "text": "test", "timestamp": "2024-01-01", "user": "alice"}
    ]

    enriched = await orchestrator.enrich_sessions(sessions, ["emotional"])

    assert enriched[0]["timestamp"] == "2024-01-01"
    assert enriched[0]["user"] == "alice"


@pytest.mark.asyncio
async def test_audit_logging_disabled():
    """Test that audit logging can be disabled."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["neutral"], "confidence": 0.5}'
    mock_response.cost_usd = 0.001

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    # Should not try to get audit
    with patch("codercrucible.enrichment.EnrichmentOrchestrator._get_audit") as mock_get_audit:
        await orchestrator.enrich_single("test", ["emotional"])
        mock_get_audit.assert_not_called()
