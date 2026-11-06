"""LangGraph state machine for autonomous lesson generation and evaluation."""

import json
import logging
from pathlib import Path
from typing import Optional
from google import genai
from langgraph.graph import END, START, StateGraph

from src.config import settings
from src.nodes.evaluator import evaluator_node
from src.nodes.generator import generator_node
from src.nodes.grounder import grounder_node
from src.nodes.planner import planner_node
from src.nodes.reviser import reviser_node
from src.nodes.router import route_after_evaluation
from src.schemas import LessonState

logger = logging.getLogger(__name__)


def build_lesson_graph(client: Optional[genai.Client] = None):
    """Compile the LangGraph cyclic workflow: Grounder -> Planner -> Generator -> Evaluator -> (Reviser -> Evaluator)* -> END."""
    workflow = StateGraph(LessonState)

    # Node wrappers passing optional client
    workflow.add_node("grounder", grounder_node)
    workflow.add_node("planner", lambda state: planner_node(state, client=client))
    workflow.add_node(
        "generator", lambda state: generator_node(state, client=client)
    )
    workflow.add_node(
        "evaluator", lambda state: evaluator_node(state, client=client)
    )
    workflow.add_node("reviser", lambda state: reviser_node(state, client=client))

    # Linear entry flow
    workflow.add_edge(START, "grounder")
    workflow.add_edge("grounder", "planner")
    workflow.add_edge("planner", "generator")
    workflow.add_edge("generator", "evaluator")

    # Cyclic conditional edge
    workflow.add_conditional_edges(
        "evaluator",
        route_after_evaluation,
        {
            "reviser": "reviser",
            "ship": END,
        },
    )

    # Loop reviser back to evaluator
    workflow.add_edge("reviser", "evaluator")

    return workflow.compile()


def save_run_outputs(state: LessonState) -> Path:
    """Save final lesson.md, rejection_log.json, and rejection_log.md to outputs/ directory."""
    out_dir = settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Best attempt selection (Amendment 10)
    best_attempt = state.get_best_attempt()
    final_content = (
        best_attempt.content
        if best_attempt
        else (state.final_lesson or "# Empty Lesson")
    )

    # Save outputs/lesson.md
    lesson_path = out_dir / "lesson.md"
    lesson_path.write_text(final_content, encoding="utf-8")
    logger.info(f"Saved final lesson to {lesson_path}")

    # 2. Build structured rejection log
    rejection_records = []
    for a in state.attempts:
        eval_data = None
        if a.evaluation:
            eval_data = {
                "passed": a.evaluation.passed,
                "failing_checks": a.evaluation.failing_checks,
                "failed_check_details": [
                    {
                        "check_id": c.check_id,
                        "reason": c.reason,
                        "evidence_quote": c.evidence_quote,
                    }
                    for c in a.evaluation.checks
                    if not c.passed
                ],
            }
        rejection_records.append(
            {
                "attempt_number": a.attempt_number,
                "timestamp": a.timestamp.isoformat(),
                "evaluation": eval_data,
                "changes_made": a.changes_made,
            }
        )

    # Save outputs/rejection_log.json
    json_path = out_dir / "rejection_log.json"
    json_path.write_text(
        json.dumps(
            {
                "run_id": state.run_id,
                "topic": state.topic,
                "status": state.status,
                "attempts_count": len(state.attempts),
                "rejection_log": rejection_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(f"Saved rejection log JSON to {json_path}")

    # 3. Save readable outputs/rejection_log.md
    md_lines = [
        f"# Rejection & Revision Log: {state.topic}",
        f"- **Run ID**: `{state.run_id}`",
        f"- **Final Status**: `{state.status.upper()}`",
        f"- **Total Attempts**: {len(state.attempts)}",
        "",
        "---",
    ]

    for a in state.attempts:
        md_lines.append(f"## Attempt {a.attempt_number}")
        if a.evaluation:
            status_badge = (
                "PASSED" if a.evaluation.passed else "FAILED"
            )
            md_lines.append(f"- **Result**: `{status_badge}`")
            if a.evaluation.failing_checks:
                md_lines.append(
                    f"- **Failing Checks**: `{', '.join(a.evaluation.failing_checks)}`"
                )
                md_lines.append("\n### Diagnostic Critique:")
                for c in a.evaluation.checks:
                    if not c.passed:
                        md_lines.append(f"- **{c.check_id}**: {c.reason}")
                        if c.evidence_quote:
                            md_lines.append(
                                f"  > *Evidence Quote:* \"{c.evidence_quote}\""
                            )
            else:
                md_lines.append("- All 10 checks passed successfully.")

        if a.changes_made:
            md_lines.append("\n### Surgical Changes Made:")
            md_lines.append(a.changes_made)

        md_lines.append("\n---\n")

    md_path = out_dir / "rejection_log.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"Saved readable rejection log MD to {md_path}")

    return lesson_path
