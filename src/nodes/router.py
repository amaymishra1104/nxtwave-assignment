"""Router Node: Conditional edge routing after evaluation.

WHY THIS NODE EXISTS:
Ensures bounded, deterministic flow control in the LangGraph cyclic loop.
Terminates immediately when all 10 checks pass, routes to the Reviser for surgical
repairs if retry budget remains (< 2), and safely exits flagged as NEEDS_HUMAN_REVIEW
with the best attempt if the retry budget is exhausted.
"""

import logging
from typing import Literal
from src.schemas import LessonState

logger = logging.getLogger(__name__)


def route_after_evaluation(
    state: LessonState,
) -> Literal["reviser", "ship"]:
    """Determine next pipeline node based on evaluation outcome and retry budget."""
    if not state.attempts:
        return "ship"

    latest_attempt = state.attempts[-1]
    if latest_attempt.evaluation and latest_attempt.evaluation.passed:
        logger.info("Evaluation PASSED on all 10 checks. Routing to finish.")
        return "ship"

    # Check retry budget
    if state.current_attempt < state.max_retries:
        logger.info(
            f"Evaluation FAILED ({len(latest_attempt.evaluation.failing_checks)} failing checks). "
            f"Attempt {state.current_attempt} < {state.max_retries}. Routing to Reviser."
        )
        return "reviser"

    # Retries exhausted
    logger.warning(
        f"Retries exhausted ({state.current_attempt} >= {state.max_retries}). "
        f"Marking status as NEEDS_HUMAN_REVIEW and selecting best attempt."
    )
    return "ship"

