"""Evaluator Node: Hybrid deterministic and LLM-judge quality assessment.

WHY THIS NODE EXISTS:
Provides the rigorous, objective grading gate that decides whether educational content
meets shipping standards without human intervention. Executes 10 hard pass/fail
rubric checks, verifies evidence quotes verbatim, and writes trace files to disk.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from google import genai

from src.checks.deterministic import (
    check_glossary_coverage,
    check_quiz_structure,
    check_reading_level,
    check_required_structure,
)
from src.checks.llm_judge import run_llm_judge
from src.config import settings
from src.schemas import CheckResult, EvaluationResult, LessonState

logger = logging.getLogger(__name__)


def evaluator_node(
    state: LessonState, client: Optional[genai.Client] = None
) -> Dict[str, Any]:
    """Evaluate the current lesson attempt against all 10 hard pass/fail rubric checkpoints."""
    current_attempt_idx = len(state.attempts) - 1
    if current_attempt_idx < 0:
        raise ValueError("Evaluator called with no attempts present in state.")

    current_attempt = state.attempts[current_attempt_idx]
    lesson_text = current_attempt.content

    logger.info(
        f"Executing Evaluator Node (Evaluating Attempt {current_attempt.attempt_number})..."
    )

    # 1. Deterministic Checks
    det_reading = check_reading_level(lesson_text, glossary=state.glossary)
    det_glossary = check_glossary_coverage(lesson_text, state.glossary)
    det_structure = check_required_structure(lesson_text)
    det_quiz = check_quiz_structure(lesson_text, required_count=3)

    # 2. LLM Judge Checks (Single structured call)
    planner_checklist = state.plan.key_concepts if state.plan else None
    llm_results = run_llm_judge(
        lesson_text=lesson_text,
        fact_pack=state.fact_pack,
        glossary=state.glossary,
        planner_checklist=planner_checklist,
        client=client,
    )

    llm_map = {r.check_id: r for r in llm_results}

    # 3. Assemble the 10 Canonical Rubric Checks
    all_checks: List[CheckResult] = []

    # Check 1: Accuracy (LLM)
    all_checks.append(
        llm_map.get(
            "accuracy",
            CheckResult(
                check_id="accuracy",
                passed=False,
                reason="Accuracy check missing from judge output.",
            ),
        )
    )

    # Check 2: What, Why, How (LLM)
    all_checks.append(
        llm_map.get(
            "what_why_how",
            CheckResult(
                check_id="what_why_how",
                passed=False,
                reason="What/Why/How check missing from judge output.",
            ),
        )
    )

    # Check 3: Key Points (LLM)
    all_checks.append(
        llm_map.get(
            "key_points",
            CheckResult(
                check_id="key_points",
                passed=False,
                reason="Key points check missing from judge output.",
            ),
        )
    )

    # Check 4: Jargon Defined (Hybrid: code first-use + LLM simplicity)
    llm_jargon = llm_map.get("jargon_defined")
    if not det_glossary.passed:
        jargon_check = det_glossary
    elif llm_jargon and not llm_jargon.passed:
        jargon_check = llm_jargon
    else:
        jargon_check = CheckResult(
            check_id="jargon_defined",
            passed=True,
            reason="All glossary terms are defined at first use with clear, simple explanations.",
            evidence_quote="",
        )
    all_checks.append(jargon_check)

    # Check 5: Reading Level (Deterministic Code)
    all_checks.append(det_reading)

    # Check 6: No Idioms (LLM)
    all_checks.append(
        llm_map.get(
            "no_idioms",
            CheckResult(
                check_id="no_idioms",
                passed=False,
                reason="Idioms check missing from judge output.",
            ),
        )
    )

    # Check 7: Worked Example (LLM)
    all_checks.append(
        llm_map.get(
            "worked_example",
            CheckResult(
                check_id="worked_example",
                passed=False,
                reason="Worked example check missing from judge output.",
            ),
        )
    )

    # Check 8: Analogy (LLM)
    all_checks.append(
        llm_map.get(
            "analogy",
            CheckResult(
                check_id="analogy",
                passed=False,
                reason="Analogy check missing from judge output.",
            ),
        )
    )

    # Check 9: Coherent Flow (LLM)
    all_checks.append(
        llm_map.get(
            "coherent_flow",
            CheckResult(
                check_id="coherent_flow",
                passed=False,
                reason="Coherent flow check missing from judge output.",
            ),
        )
    )

    # Check 10: Wrap-Up (Hybrid: code structure + 3 questions + LLM pedagogy)
    llm_wrap_up = llm_map.get("wrap_up")
    if not det_structure.passed:
        wrap_up_check = CheckResult(
            check_id="wrap_up",
            passed=False,
            reason=det_structure.reason,
            evidence_quote="",
        )
    elif not det_quiz.passed:
        wrap_up_check = det_quiz
    elif llm_wrap_up and not llm_wrap_up.passed:
        wrap_up_check = llm_wrap_up
    else:
        wrap_up_check = CheckResult(
            check_id="wrap_up",
            passed=True,
            reason="Concludes with summary and exactly 3 conceptual self-check questions.",
            evidence_quote="",
        )
    all_checks.append(wrap_up_check)

    # Determine overall evaluation pass/fail
    failing = [c.check_id for c in all_checks if not c.passed]
    evaluation_result = EvaluationResult(
        passed=len(failing) == 0,
        checks=all_checks,
        failing_checks=failing,
    )

    # Update attempt with evaluation result
    current_attempt.evaluation = evaluation_result
    updated_attempts = list(state.attempts)
    updated_attempts[current_attempt_idx] = current_attempt

    # Write trace file to outputs/runs/<run_id>/attempt_<n>.json
    trace_dir = settings.output_dir / "runs" / state.run_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"attempt_{current_attempt.attempt_number}.json"

    trace_data = {
        "run_id": state.run_id,
        "attempt_number": current_attempt.attempt_number,
        "passed": evaluation_result.passed,
        "failing_checks": evaluation_result.failing_checks,
        "changes_made": current_attempt.changes_made,
        "checks": [c.model_dump() for c in all_checks],
        "content": lesson_text,
    }
    trace_file.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")
    logger.info(f"Saved attempt trace to {trace_file}")

    new_status = "passed" if evaluation_result.passed else "revising"

    return {
        "attempts": updated_attempts,
        "status": new_status,
        "final_lesson": lesson_text if evaluation_result.passed else state.final_lesson,
    }

