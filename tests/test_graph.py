"""Integration and unit tests for the LangGraph pipeline (M4)."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.graph import build_lesson_graph, save_run_outputs
from src.nodes.router import route_after_evaluation
from src.schemas import (
    CheckResult,
    EvaluationResult,
    LessonAttempt,
    LessonPlan,
    LessonState,
)


def test_router_branching_logic():
    """Verify conditional edge router under all conditions."""
    # 1. Passed -> ship
    state_passed = LessonState(
        current_attempt=0,
        max_retries=2,
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="Lesson text",
                evaluation=EvaluationResult(passed=True, checks=[]),
            )
        ],
    )
    assert route_after_evaluation(state_passed) == "ship"

    # 2. Failed with retries available -> reviser
    state_failed_retry = LessonState(
        current_attempt=0,
        max_retries=2,
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="Lesson text",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[
                        CheckResult(
                            check_id="accuracy", passed=False, reason="error"
                        )
                    ],
                    failing_checks=["accuracy"],
                ),
            )
        ],
    )
    assert route_after_evaluation(state_failed_retry) == "reviser"

    # 3. Failed with retries exhausted (attempt >= 2) -> ship (NEEDS_HUMAN_REVIEW)
    state_exhausted = LessonState(
        current_attempt=2,
        max_retries=2,
        attempts=[
            LessonAttempt(
                attempt_number=2,
                content="Lesson text",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[
                        CheckResult(
                            check_id="accuracy", passed=False, reason="error"
                        )
                    ],
                    failing_checks=["accuracy"],
                ),
            )
        ],
    )
    assert route_after_evaluation(state_exhausted) == "ship"


def test_best_attempt_selection_fewest_failing_checks():
    """Amendment 10: Best attempt must be the one with fewest failing checks."""
    state = LessonState(
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="Attempt 0 content",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[],
                    failing_checks=["accuracy", "no_idioms", "reading_level"],
                ),
            ),
            LessonAttempt(
                attempt_number=1,
                content="Attempt 1 content",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[],
                    failing_checks=["accuracy"],  # Fewest failing checks!
                ),
            ),
            LessonAttempt(
                attempt_number=2,
                content="Attempt 2 content",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[],
                    failing_checks=["reading_level", "jargon_defined"],
                ),
            ),
        ]
    )

    best = state.get_best_attempt()
    assert best is not None
    assert best.attempt_number == 1
    assert best.content == "Attempt 1 content"


def test_save_run_outputs_creates_all_files(tmp_path, monkeypatch):
    """Verify outputs/lesson.md, rejection_log.json, and rejection_log.md are written."""
    from src.config import settings

    monkeypatch.setattr(settings, "output_dir", tmp_path)

    state = LessonState(
        run_id="test_run_123",
        topic="Introduction to RAG",
        status="passed",
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="# Introduction to RAG\n\nGreat content here.",
                evaluation=EvaluationResult(
                    passed=True,
                    checks=[
                        CheckResult(
                            check_id="accuracy",
                            passed=True,
                            reason="Accurate.",
                        )
                    ],
                    failing_checks=[],
                ),
            )
        ],
    )

    lesson_file = save_run_outputs(state)
    assert lesson_file.exists()
    assert (tmp_path / "rejection_log.json").exists()
    assert (tmp_path / "rejection_log.md").exists()

    json_content = json.loads(
        (tmp_path / "rejection_log.json").read_text(encoding="utf-8")
    )
    assert json_content["run_id"] == "test_run_123"
    assert json_content["status"] == "passed"


def test_mocked_end_to_end_graph_execution():
    """Verify full LangGraph loop execution using a mock Gemini client."""
    golden_lesson = Path("tests/good_lessons/good_rag_lesson.md").read_text(
        encoding="utf-8"
    )

    mock_client = MagicMock()

    # Planner response
    plan_mock = LessonPlan(
        topic="Introduction to RAG",
        what_why_how={
            "what": "What is RAG",
            "why": "Why it matters",
            "how": "How it works",
        },
        key_concepts=[
            "retrieval",
            "embeddings",
            "vector database",
            "chunking",
            "augmenting the prompt",
            "generation",
            "hallucination reduction",
            "limitations",
        ],
        outline=["Intro", "What", "How", "Example", "Quiz"],
    )

    # Judge response (all passing)
    judge_mock_response = {
        "checks": [
            {
                "check_id": "accuracy",
                "passed": True,
                "reason": "Accurate.",
                "evidence_quote": "",
            },
            {
                "check_id": "what_why_how",
                "passed": True,
                "reason": "Covers what why how.",
                "evidence_quote": "",
            },
            {
                "check_id": "key_points",
                "passed": True,
                "reason": "Covers all key points.",
                "evidence_quote": "",
            },
            {
                "check_id": "jargon_defined",
                "passed": True,
                "reason": "All terms defined.",
                "evidence_quote": "",
            },
            {
                "check_id": "no_idioms",
                "passed": True,
                "reason": "No idioms.",
                "evidence_quote": "",
            },
            {
                "check_id": "worked_example",
                "passed": True,
                "reason": "Includes worked example.",
                "evidence_quote": "",
            },
            {
                "check_id": "analogy",
                "passed": True,
                "reason": "Includes open-book analogy.",
                "evidence_quote": "",
            },
            {
                "check_id": "coherent_flow",
                "passed": True,
                "reason": "Good flow.",
                "evidence_quote": "",
            },
            {
                "check_id": "wrap_up",
                "passed": True,
                "reason": "Good wrap up.",
                "evidence_quote": "",
            },
        ]
    }

    # Sequence of client calls:
    # 1. planner: returns plan_mock json
    # 2. generator: returns golden_lesson text
    # 3. evaluator (LLM judge): returns judge_mock_response json
    mock_client.models.generate_content.side_effect = [
        MagicMock(text=plan_mock.model_dump_json()),
        MagicMock(text=golden_lesson),
        MagicMock(text=json.dumps(judge_mock_response)),
    ]

    graph = build_lesson_graph(client=mock_client)
    initial_state = LessonState(
        topic="Introduction to RAG",
        max_retries=2,
    )

    final_state_dict = graph.invoke(initial_state)
    final_state = (
        LessonState(**final_state_dict)
        if isinstance(final_state_dict, dict)
        else final_state_dict
    )

    assert len(final_state.attempts) == 1
    assert final_state.status == "passed"
    assert final_state.attempts[0].evaluation.passed is True
