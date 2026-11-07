"""Tests for the LLM Judge module (M3).

Default pytest runs use mocks for fast, reliable unit testing.
Live API tests are decorated with @pytest.mark.live.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.checks.llm_judge import (
    verify_evidence_quote,
    build_judge_prompt,
    run_llm_judge,
    LLMJudgeBatchResponse,
    LLMCheckItem,
)
from src.schemas import FactItem


def test_verify_evidence_quote():
    """Verify evidence quote checking logic per Amendment 1."""
    lesson = """
In this lesson, we explore Retrieval-Augmented Generation.
RAG does not retrain the model weights.
It searches your documents first.
"""
    # 1. Empty quote is allowed for missing element failures
    assert verify_evidence_quote("", lesson) is True
    assert verify_evidence_quote("   ", lesson) is True

    # 2. Exact substring match
    assert verify_evidence_quote("RAG does not retrain the model weights.", lesson) is True

    # 3. Whitespace-normalized match (e.g. newline to space)
    assert verify_evidence_quote("Retrieval-Augmented Generation. RAG does not", lesson) is True

    # 4. Fabricated quote must fail
    assert verify_evidence_quote("RAG retrains the model completely every night.", lesson) is False


def test_missing_api_key_raises_clear_error(monkeypatch):
    """Verify clear error message when GEMINI_API_KEY is not set."""
    from src.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", None)
    with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
        run_llm_judge(
            lesson_text="Some text",
            fact_pack=[],
            client=None,
        )


def test_mocked_llm_judge_success():
    """Verify successful LLM judge execution using a mocked Gemini client."""
    mock_response_data = {
        "checks": [
            {
                "check_id": "accuracy",
                "passed": True,
                "reason": "Accurately represents RAG mechanisms and does not state model weights are modified.",
                "evidence_quote": "",
            },
            {
                "check_id": "what_why_how",
                "passed": True,
                "reason": "What, why, and how are clearly addressed in dedicated sections.",
                "evidence_quote": "",
            },
            {
                "check_id": "key_points",
                "passed": True,
                "reason": "All 8 key technical concepts are covered.",
                "evidence_quote": "",
            },
            {
                "check_id": "jargon_defined",
                "passed": True,
                "reason": "All technical terms are clearly defined.",
                "evidence_quote": "",
            },
            {
                "check_id": "no_idioms",
                "passed": True,
                "reason": "No confusing Western idioms found.",
                "evidence_quote": "",
            },
            {
                "check_id": "worked_example",
                "passed": True,
                "reason": "Includes Delhi State University chatbot worked example.",
                "evidence_quote": "",
            },
            {
                "check_id": "analogy",
                "passed": True,
                "reason": "Includes open-book exam analogy.",
                "evidence_quote": "",
            },
            {
                "check_id": "coherent_flow",
                "passed": True,
                "reason": "Concepts are introduced sequentially.",
                "evidence_quote": "",
            },
            {
                "check_id": "wrap_up",
                "passed": True,
                "reason": "Self-check questions assess core concepts without prior knowledge.",
                "evidence_quote": "",
            },
        ]
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(mock_response_data)
    )

    lesson_text = "Sample lesson text that includes all required elements."
    fact_pack = [
        FactItem(
            id="f1",
            fact="RAG does not modify model weights.",
            source_name="Lewis et al.",
            source_url="https://arxiv.org/abs/2005.11401",
            category="architecture",
        )
    ]

    results = run_llm_judge(
        lesson_text=lesson_text,
        fact_pack=fact_pack,
        client=mock_client,
    )

    assert len(results) == 9
    assert all(r.passed for r in results)
    assert mock_client.models.generate_content.called


def test_mocked_llm_judge_catches_violation_with_quote():
    """Verify failing check extracts verbatim evidence quote."""
    lesson_text = (
        "In this system, RAG works by retraining the entire model weights on your PDF documents."
    )

    mock_response_data = {
        "checks": [
            {
                "check_id": "accuracy",
                "passed": False,
                "reason": "Claims model weights are retrained. Occurs in paragraph 1. Must clarify that weights remain frozen.",
                "evidence_quote": "RAG works by retraining the entire model weights on your PDF documents.",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(mock_response_data)
    )

    results = run_llm_judge(
        lesson_text=lesson_text,
        fact_pack=[],
        client=mock_client,
    )

    assert len(results) == 1
    accuracy_check = results[0]
    assert accuracy_check.check_id == "accuracy"
    assert accuracy_check.passed is False
    assert (
        accuracy_check.evidence_quote
        == "RAG works by retraining the entire model weights on your PDF documents."
    )


def test_mocked_llm_judge_handles_hallucinated_quote_retry_and_judge_error():
    """Verify that if judge hallucinates a quote, it retries once, then flags judge_error."""
    lesson_text = "Here is some real text from the lesson draft."

    # Return a quote that does NOT exist in lesson_text
    mock_response_data = {
        "checks": [
            {
                "check_id": "no_idioms",
                "passed": False,
                "reason": "Contains idiom. Occurs in section 2. Remove idiom.",
                "evidence_quote": "This phrase never existed in the lesson!",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(mock_response_data)
    )

    results = run_llm_judge(
        lesson_text=lesson_text,
        fact_pack=[],
        client=mock_client,
        max_retries=1,
    )

    # Should attempt generation, detect quote mismatch, retry once, and then mark JUDGE_ERROR
    assert mock_client.models.generate_content.call_count == 2
    assert len(results) == 1
    assert results[0].passed is False
    assert "JUDGE_ERROR" in results[0].reason


@pytest.mark.live
def test_live_gemini_judge_call():
    """Live integration test calling real Gemini API.

    Run explicitly with: pytest -m live tests/test_llm_judge.py
    Requires GEMINI_API_KEY in environment or .env.
    """
    from src.config import settings

    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not configured for live test")

    lesson_path = "tests/good_lessons/good_rag_lesson.md"
    with open(lesson_path, "r", encoding="utf-8") as f:
        lesson_text = f.read()

    with open("data/fact_pack.json", "r", encoding="utf-8") as f:
        raw_facts = json.load(f)
        fact_pack = [FactItem(**item) for item in raw_facts]

    results = run_llm_judge(lesson_text=lesson_text, fact_pack=fact_pack)
    assert len(results) >= 7
    # All checks should pass on golden lesson
    assert all(r.passed for r in results)

