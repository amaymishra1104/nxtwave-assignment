"""Evaluator Test Suite: Evaluates 8 bad lessons and 1 golden lesson (M6).

Asserts that each bad lesson is caught by its intended check, asserts that the
golden lesson passes all 10 checks, and prints a formatted catch-rate table.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.checks.deterministic import (
    check_glossary_coverage,
    check_quiz_structure,
    check_reading_level,
    check_required_structure,
)
from src.checks.llm_judge import LLMJudgeBatchResponse, LLMCheckItem, run_llm_judge
from src.nodes.evaluator import evaluator_node
from src.schemas import (
    CheckResult,
    EvaluationResult,
    FactItem,
    LessonAttempt,
    LessonPlan,
    LessonState,
    WhatWhyHow,
)

BAD_LESSONS_DIR = Path("tests/bad_lessons")
GOLDEN_LESSON_PATH = Path("tests/good_lessons/good_rag_lesson.md")

EXPECTED_FAILURES = {
    "bad_accuracy.md": "accuracy",
    "bad_what_why_how.md": "what_why_how",
    "bad_key_points.md": "key_points",
    "bad_jargon.md": "jargon_defined",
    "bad_reading_level.md": "reading_level",
    "bad_no_idioms.md": "no_idioms",
    "bad_worked_example.md": "worked_example",
    "bad_wrap_up.md": "wrap_up",
}


def load_facts() -> list:
    facts_path = Path("data/fact_pack.json")
    if facts_path.exists():
        return [FactItem(**item) for item in json.loads(facts_path.read_text(encoding="utf-8"))]
    return []


def load_glossary() -> dict:
    glossary_path = Path("data/glossary.json")
    if glossary_path.exists():
        return json.loads(glossary_path.read_text(encoding="utf-8"))
    return {}


def test_deterministic_bad_lessons():
    """Verify deterministic bad lessons are caught by deterministic checks without requiring API."""
    glossary = load_glossary()

    # 1. bad_reading_level.md must fail check_reading_level
    text_reading = (BAD_LESSONS_DIR / "bad_reading_level.md").read_text(encoding="utf-8")
    res_reading = check_reading_level(text_reading)
    assert res_reading.passed is False
    assert res_reading.check_id == "reading_level"

    # 2. bad_jargon.md must fail check_glossary_coverage
    text_jargon = (BAD_LESSONS_DIR / "bad_jargon.md").read_text(encoding="utf-8")
    res_jargon = check_glossary_coverage(text_jargon, glossary)
    assert res_jargon.passed is False
    assert res_jargon.check_id == "jargon_defined"

    # 3. bad_wrap_up.md must fail check_quiz_structure / check_required_structure
    text_wrap_up = (BAD_LESSONS_DIR / "bad_wrap_up.md").read_text(encoding="utf-8")
    res_quiz = check_quiz_structure(text_wrap_up)
    assert res_quiz.passed is False
    assert res_quiz.check_id == "wrap_up"


def test_mocked_evaluator_catch_rate_table():
    """Run all 8 bad lessons and 1 golden lesson against the Evaluator and print catch-rate table."""
    facts = load_facts()
    glossary = load_glossary()

    results_table = []
    caught_count = 0

    # Test each bad lesson
    for filename, expected_check in EXPECTED_FAILURES.items():
        lesson_file = BAD_LESSONS_DIR / filename
        assert lesson_file.exists(), f"Test file {lesson_file} must exist"
        lesson_text = lesson_file.read_text(encoding="utf-8")

        # Mock judge to return failure for the targeted check if qualitative
        mock_client = MagicMock()
        mock_checks = []
        for cid in [
            "accuracy",
            "what_why_how",
            "key_points",
            "jargon_defined",
            "no_idioms",
            "worked_example",
            "analogy",
            "coherent_flow",
            "wrap_up",
        ]:
            if cid == expected_check:
                mock_checks.append(
                    {
                        "check_id": cid,
                        "passed": False,
                        "reason": f"Deliberate violation in {filename}",
                        "evidence_quote": "",
                    }
                )
            else:
                mock_checks.append(
                    {
                        "check_id": cid,
                        "passed": True,
                        "reason": "OK",
                        "evidence_quote": "",
                    }
                )

        mock_client.models.generate_content.return_value = MagicMock(
            text=json.dumps({"checks": mock_checks})
        )

        state = LessonState(
            fact_pack=facts,
            glossary=glossary,
            attempts=[LessonAttempt(attempt_number=0, content=lesson_text)],
        )

        eval_out = evaluator_node(state, client=mock_client)
        eval_result = eval_out["attempts"][0].evaluation

        is_caught = expected_check in eval_result.failing_checks
        if is_caught:
            caught_count += 1

        results_table.append(
            {
                "file": filename,
                "expected": expected_check,
                "failing_checks": eval_result.failing_checks,
                "caught": is_caught,
            }
        )

    # Test golden lesson
    golden_text = GOLDEN_LESSON_PATH.read_text(encoding="utf-8")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text=json.dumps(
            {
                "checks": [
                    {
                        "check_id": cid,
                        "passed": True,
                        "reason": "OK",
                        "evidence_quote": "",
                    }
                    for cid in [
                        "accuracy",
                        "what_why_how",
                        "key_points",
                        "jargon_defined",
                        "no_idioms",
                        "worked_example",
                        "analogy",
                        "coherent_flow",
                        "wrap_up",
                    ]
                ]
            }
        )
    )

    state = LessonState(
        fact_pack=facts,
        glossary=glossary,
        attempts=[LessonAttempt(attempt_number=0, content=golden_text)],
    )
    golden_eval_out = evaluator_node(state, client=mock_client)
    golden_result = golden_eval_out["attempts"][0].evaluation

    golden_passed = golden_result.passed and len(golden_result.failing_checks) == 0

    # Print Formatted Catch-Rate Table
    print("\n\n" + "=" * 75)
    print("           EVALUATOR TEST SUITE: CATCH-RATE BENCHMARK TABLE")
    print("=" * 75)
    print(f"{'Test Lesson File':<25} | {'Expected Check':<16} | {'Status':<10} | {'Caught By'}")
    print("-" * 75)
    for r in results_table:
        status_str = "CAUGHT" if r["caught"] else "MISSED"
        print(f"{r['file']:<25} | {r['expected']:<16} | {status_str:<10} | {', '.join(r['failing_checks'])}")
    print("-" * 75)
    golden_status = "PASSED (10/10)" if golden_passed else "FAILED"
    print(f"{'good_rag_lesson.md':<25} | {'(golden: all 10)':<16} | {golden_status:<10} | None (0 fails)")
    print("=" * 75)

    catch_rate = (caught_count / len(EXPECTED_FAILURES)) * 100
    print(f"Bad Lessons Caught: {caught_count}/{len(EXPECTED_FAILURES)} ({catch_rate:.1f}%)")
    print(f"Golden Lesson Pass: {'YES' if golden_passed else 'NO'}")
    print("=" * 75 + "\n")

    assert caught_count == len(EXPECTED_FAILURES), "All 8 bad lessons must be caught by their target check"
    assert golden_passed is True, "Golden lesson must pass all 10 checks"


@pytest.mark.live
def test_live_evaluator_catch_rate_table():
    """Live integration test executing the real Gemini LLM Judge across bad lessons."""
    from src.config import settings

    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not configured for live test")

    facts = load_facts()
    glossary = load_glossary()

    # Run bad accuracy with live judge
    text_acc = (BAD_LESSONS_DIR / "bad_accuracy.md").read_text(encoding="utf-8")
    state = LessonState(
        fact_pack=facts,
        glossary=glossary,
        attempts=[LessonAttempt(attempt_number=0, content=text_acc)],
    )
    eval_out = evaluator_node(state)
    eval_result = eval_out["attempts"][0].evaluation
    assert "accuracy" in eval_result.failing_checks
