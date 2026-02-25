"""
Enrichment module for CoderCrucible.

Provides semantic enrichment for conversations including:
- Emotional tags
- Security flags
- Intent classification

These enrichments provide the semantic understanding needed for /think-cheap.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel


class IntentType(str, Enum):
    """Intent types for conversation classification."""

    DEBUG = "debug"
    FEATURE = "feature"
    QUESTION = "question"
    VENT = "vent"
    EXPLORATION = "exploration"
    OTHER = "other"


class EmotionalEnrichment(BaseModel):
    """Emotional enrichment for conversations."""

    emotional_tags: List[str]
    confidence: float


class SecurityEnrichment(BaseModel):
    """Security enrichment for conversations."""

    security_issues: List[str]
    confidence: float
    excerpts: Optional[List[str]] = None


class IntentEnrichment(BaseModel):
    """Intent enrichment for conversations."""

    intent: IntentType
    confidence: float


EMOTIONAL_PROMPT = """You are analyzing a conversation between a user and an AI coding assistant.
Extract the emotional states expressed by the user in this conversation.
Return a JSON object with:
- "emotional_tags": list of emotions (choose from: frustration, excitement, confusion, relief, curiosity, satisfaction, anger, anxiety, happiness, sadness, surprise, disgust, fear, neutral)
- "confidence": float between 0 and 1

Conversation:
{text}
"""

SECURITY_PROMPT = """Analyze the following conversation for any potential security issues not caught by standard regex patterns.
Look for:
- Accidental exposure of API keys, tokens, passwords in unusual formats
- Mention of internal IP addresses, hostnames, or infrastructure details
- Discussion of security vulnerabilities or exploits
- Code snippets that contain hardcoded secrets
Return a JSON object with:
- "security_issues": list of strings describing each issue found
- "confidence": float between 0 and 1
- "excerpts": list of strings showing the context (optional)

Conversation:
{text}
"""

INTENT_PROMPT = """You are analyzing a conversation between a user and an AI coding assistant.
Classify the user's primary intent in this conversation.
Return a JSON object with:
- "intent": one of: debug, feature, question, vent, exploration, other
- "confidence": float between 0 and 1

Conversation:
{text}
"""

# Dimension to prompt mapping
DIMENSION_PROMPTS = {
    "emotional": EMOTIONAL_PROMPT,
    "security": SECURITY_PROMPT,
    "intent": INTENT_PROMPT,
}


def _parse_enrichment_response(
    response: Any, dimension: str
) -> EmotionalEnrichment | SecurityEnrichment | IntentEnrichment:
    """Parse LLM response into appropriate enrichment model."""
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, AttributeError, ValueError):
        # Fallback to defaults
        if dimension == "emotional":
            return EmotionalEnrichment(emotional_tags=["neutral"], confidence=0.0)
        elif dimension == "security":
            return SecurityEnrichment(security_issues=[], confidence=0.0)
        else:
            return IntentEnrichment(intent=IntentType.OTHER, confidence=0.0)

    if dimension == "emotional":
        return EmotionalEnrichment(
            emotional_tags=data.get("emotional_tags", []),
            confidence=float(data.get("confidence", 0.0)),
        )
    elif dimension == "security":
        return SecurityEnrichment(
            security_issues=data.get("security_issues", []),
            confidence=float(data.get("confidence", 0.0)),
            excerpts=data.get("excerpts"),
        )
    else:  # intent
        try:
            intent = IntentType(data.get("intent", "other"))
        except ValueError:
            intent = IntentType.OTHER
        return IntentEnrichment(
            intent=intent,
            confidence=float(data.get("confidence", 0.0)),
        )


class EnrichmentOrchestrator:
    """
    Orchestrates enrichment of conversations across multiple dimensions.

    This class handles batching and parallel processing of enrichment
    calls to the LLM. It integrates with:
    - scout.llm.batch for efficient batch processing
    - scout.audit for cost tracking and logging

    Example usage:

    ```python
    orchestrator = EnrichmentOrchestrator(
        llm_call=my_llm_call,
        batch_size=10,
        max_concurrent=5
    )

    sessions = [{"id": "1", "text": "..."}, {"id": "2", "text": "..."}]
    enriched = await orchestrator.enrich_sessions(
        sessions,
        dimensions=["emotional", "security", "intent"]
    )
    ```
    """

    def __init__(
        self,
        llm_call: Callable,
        batch_size: int = 10,
        max_concurrent: int = 5,
        audit_logging: bool = True,
    ):
        """
        Initialize the enrichment orchestrator.

        Args:
            llm_call: Callable for making LLM requests. Must return an object
                     with 'content' (str) and 'cost_usd' (float) attributes.
            batch_size: Number of sessions to process in a batch.
            max_concurrent: Maximum number of concurrent LLM calls.
            audit_logging: Whether to log enrichment costs to audit.
        """
        self.llm_call = llm_call
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.audit_logging = audit_logging
        self._audit = None

    def _get_audit(self):
        """Lazy-load audit instance to avoid import cycles."""
        if self._audit is None:
            try:
                from scout.audit import get_audit
                self._audit = get_audit()
            except ImportError:
                pass
        return self._audit

    def _log_enrichment(
        self,
        dimension: str,
        session_id: str,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ):
        """Log enrichment cost to audit."""
        if not self.audit_logging:
            return
        audit = self._get_audit()
        if audit is None:
            return
        try:
            audit.log(
                "enrich",
                cost=cost_usd,
                model=model,
                input_t=input_tokens,
                output_t=output_tokens,
                dimension=dimension,
                session_id=session_id,
            )
        except Exception:
            pass  # Don't fail enrichment if audit fails

    async def _enrich_single_dimension(
        self,
        text: str,
        dimension: str,
        session_id: str,
        model: str = "llama-3.1-8b-instant",
    ) -> tuple[str, Any]:
        """Enrich a single text for one dimension."""
        prompt_template = DIMENSION_PROMPTS.get(dimension)
        if not prompt_template:
            return dimension, None

        prompt = prompt_template.format(text=text)
        response = await self.llm_call(
            prompt=prompt,
            model=model,
            temperature=0.0,
        )

        # Log to audit
        self._log_enrichment(
            dimension=dimension,
            session_id=session_id,
            cost_usd=getattr(response, "cost_usd", 0.0),
            input_tokens=getattr(response, "input_tokens", 0),
            output_tokens=getattr(response, "output_tokens", 0),
            model=getattr(response, "model", model),
        )

        return dimension, _parse_enrichment_response(response, dimension)

    async def enrich_sessions(
        self,
        sessions: List[Dict[str, Any]],
        dimensions: List[str],
        model: str = "llama-3.1-8b-instant",
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple sessions with the specified dimensions.

        Uses batch processing for efficiency with concurrency control.

        Args:
            sessions: List of session dictionaries with at least 'id' and 'text'.
            dimensions: List of enrichment dimensions to apply.
                       Supported: "emotional", "security", "intent"
            model: LLM model to use for enrichment.

        Returns:
            List of sessions with enrichment data added.
        """
        if not sessions or not dimensions:
            return sessions

        # Build list of (session_id, text, dimension) tuples
        tasks = []
        for session in sessions:
            session_id = session.get("id", "unknown")
            text = session.get("text", "")
            for dimension in dimensions:
                tasks.append((session_id, text, dimension))

        if not tasks:
            return sessions

        # Process all enrichment tasks with concurrency control
        import asyncio

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_enrich(session_id: str, text: str, dimension: str):
            async with semaphore:
                return await self._enrich_single_dimension(
                    text, dimension, session_id, model
                )

        task_results = await asyncio.gather(
            *[bounded_enrich(sid, text, dim) for sid, text, dim in tasks],
            return_exceptions=True,
        )

        # Organize results by session
        session_enrichments: Dict[str, Dict[str, Any]] = {}
        for session in sessions:
            session_id = session.get("id", "unknown")
            session_enrichments[session_id] = {}

        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                continue
            dimension, enrichment = result
            session_id = tasks[i][0]
            if enrichment is not None:
                session_enrichments[session_id][dimension] = enrichment

        # Merge enrichments into sessions
        enriched_sessions = []
        for session in sessions:
            session_id = session.get("id", "unknown")
            enriched = session.copy()
            enriched["enrichments"] = session_enrichments.get(session_id, {})
            enriched_sessions.append(enriched)

        return enriched_sessions

    async def enrich_single(
        self,
        text: str,
        dimensions: List[str],
        session_id: str = "single",
        model: str = "llama-3.1-8b-instant",
    ) -> Dict[str, Any]:
        """
        Enrich a single text with the specified dimensions.

        Args:
            text: The text to enrich.
            dimensions: List of enrichment dimensions to apply.
            session_id: Optional session ID for audit logging.
            model: LLM model to use for enrichment.

        Returns:
            Dictionary with enrichment results.
        """
        result = {}

        for dimension in dimensions:
            _, enrichment = await self._enrich_single_dimension(
                text, dimension, session_id, model
            )
            if enrichment is not None:
                result[dimension] = enrichment

        return result


def get_enrichment_prompt(dimension: str) -> str:
    """
    Get the prompt template for a given enrichment dimension.

    Args:
        dimension: The enrichment dimension ("emotional", "security", "intent")

    Returns:
        The prompt template string.
    """
    return DIMENSION_PROMPTS.get(dimension, "")
