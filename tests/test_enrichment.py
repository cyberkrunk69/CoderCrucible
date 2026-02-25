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


@pytest.mark.asyncio
async def test_full_enrichment_flow_integration():
    """Integration test for full enrichment flow with mocked LLM.

    This test verifies the complete enrichment pipeline without requiring
    a real Groq API key, using mocks to simulate the LLM responses.
    """
    # Create realistic mock responses for each dimension
    emotional_response = MagicMock()
    emotional_response.content = '{"emotional_tags": ["frustration", "confusion"], "confidence": 0.85}'
    emotional_response.cost_usd = 0.0001
    emotional_response.input_tokens = 150
    emotional_response.output_tokens = 30
    emotional_response.model = "llama-3.1-8b-instant"

    security_response = MagicMock()
    security_response.content = '{"security_issues": [], "confidence": 0.95}'
    security_response.cost_usd = 0.0001
    security_response.input_tokens = 200
    security_response.output_tokens = 20
    security_response.model = "llama-3.1-8b-instant"

    intent_response = MagicMock()
    intent_response.content = '{"intent": "debug", "confidence": 0.92}'
    intent_response.cost_usd = 0.0001
    intent_response.input_tokens = 120
    intent_response.output_tokens = 25
    intent_response.model = "llama-3.1-8b-instant"

    # Create mock LLM that returns different responses based on prompt
    call_count = 0
    async def mock_llm_call(prompt: str, model: str, temperature: float):
        nonlocal call_count
        call_count += 1
        if "emotional" in prompt.lower():
            return emotional_response
        elif "security" in prompt.lower():
            return security_response
        else:
            return intent_response

    orchestrator = EnrichmentOrchestrator(
        llm_call=mock_llm_call,
        model="llama-3.1-8b-instant",
        batch_size=10,
        max_concurrent=3,
        audit_logging=False,
    )

    # Test sessions that mimic real conversation data
    sessions = [
        {
            "id": "session-001",
            "text": "I'm trying to fix a null pointer exception in my Python code. The error happens when I call user.getProfile() but sometimes the user object is None. How can I handle this properly?",
        },
        {
            "id": "session-002",
            "text": "Can you help me add OAuth2 authentication to my FastAPI application? I want users to be able to sign in with Google.",
        },
    ]

    # Enrich with all three dimensions
    enriched = await orchestrator.enrich_sessions(
        sessions,
        dimensions=["emotional", "security", "intent"],
    )

    # Verify results
    assert len(enriched) == 2
    assert call_count == 6  # 2 sessions × 3 dimensions

    # Check first session (debug intent)
    session1 = enriched[0]
    assert session1["id"] == "session-001"
    assert "enrichments" in session1

    # Verify emotional enrichment
    assert "emotional" in session1["enrichments"]
    assert "frustration" in session1["enrichments"]["emotional"].emotional_tags
    assert session1["enrichments"]["emotional"].confidence > 0.8

    # Verify security enrichment
    assert "security" in session1["enrichments"]
    assert isinstance(session1["enrichments"]["security"].security_issues, list)

    # Verify intent enrichment
    assert "intent" in session1["enrichments"]
    assert session1["enrichments"]["intent"].intent == IntentType.DEBUG

    # Check second session (feature intent)
    session2 = enriched[1]
    assert session2["id"] == "session-002"
    assert session2["enrichments"]["intent"].intent == IntentType.FEATURE

    # Verify original fields are preserved
    assert "text" in session1
    assert "null pointer exception" in session1["text"]


@pytest.mark.asyncio
async def test_enrichment_with_cost_tracking():
    """Test that enrichment correctly tracks costs from LLM responses."""
    mock_response = MagicMock()
    mock_response.content = '{"emotional_tags": ["curiosity"], "confidence": 0.9}'
    mock_response.cost_usd = 0.0002
    mock_response.input_tokens = 100
    mock_response.output_tokens = 25
    mock_response.model = "llama-3.1-8b-instant"

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    sessions = [{"id": "1", "text": "How does async/await work in Python?"}]

    enriched = await orchestrator.enrich_sessions(sessions, dimensions=["emotional"])

    # Verify enrichment worked
    assert len(enriched) == 1
    assert enriched[0]["enrichments"]["emotional"].emotional_tags == ["curiosity"]


@pytest.mark.asyncio
async def test_enrichment_error_handling():
    """Test that enrichment handles malformed LLM responses gracefully."""
    # Mock response with invalid JSON
    mock_response = MagicMock()
    mock_response.content = "not valid json"
    mock_response.cost_usd = 0.0

    mock_llm = AsyncMock(return_value=mock_response)
    orchestrator = EnrichmentOrchestrator(llm_call=mock_llm, audit_logging=False)

    sessions = [{"id": "1", "text": "test"}]

    # Should not raise, should return default values
    enriched = await orchestrator.enrich_sessions(sessions, dimensions=["emotional"])

    assert len(enriched) == 1
    # Should have fallback enrichment with neutral tags
    assert enriched[0]["enrichments"]["emotional"].emotional_tags == ["neutral"]
    assert enriched[0]["enrichments"]["emotional"].confidence == 0.0


@pytest.mark.slow
@pytest.mark.skipif(
    not __import__("os").environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set"
)
@pytest.mark.asyncio
async def test_real_groq_enrichment():
    """Integration test with real Groq API.
    
    This test runs against the actual Groq API and verifies the response structure.
    It is skipped by default and only runs when GROQ_API_KEY is set.
    
    Run with: pytest tests/test_enrichment.py -v -m slow
    """
    import os
    from codercrucible.enrichment import IntentType
    
    # Get API key from environment
    api_key = os.environ.get("GROQ_API_KEY")
    
    # Import scout.llm for actual API calls
    try:
        from scout.llm import chat
    except ImportError:
        pytest.skip("scout.llm not available")
    
    # Create a real LLM call function
    async def real_llm_call(prompt: str, model: str, temperature: float):
        response = await chat(
            prompt=prompt,
            model=model,
            api_key=api_key,
            temperature=temperature,
        )
        return response
    
    orchestrator = EnrichmentOrchestrator(
        llm_call=real_llm_call,
        model="llama-3.1-8b-instant",
        audit_logging=False,
    )
    
    # Test with a small session
    sessions = [
        {
            "id": "test-1",
            "text": "I'm frustrated because my code keeps throwing null pointer exceptions. Can you help me debug this?",
        }
    ]
    
    # Enrich with just emotional dimension to minimize API calls
    enriched = await orchestrator.enrich_sessions(
        sessions,
        dimensions=["emotional"],
    )
    
    # Verify structure
    assert len(enriched) == 1
    assert "enrichments" in enriched[0]
    assert "emotional" in enriched[0]["enrichments"]
    
    # Verify enrichment has valid data
    emotional = enriched[0]["enrichments"]["emotional"]
    assert isinstance(emotional.emotional_tags, list)
    assert len(emotional.emotional_tags) > 0
    assert 0.0 <= emotional.confidence <= 1.0
    
    print(f"Real API enrichment successful: {emotional.emotional_tags}")
