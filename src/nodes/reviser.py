"""Reviser Node: Performs surgical, targeted revisions on failing lesson checks.

WHY THIS NODE EXISTS:
Prevents destructive regeneration loops. Instead of blindly rewriting the entire
document from scratch—which frequently breaks sections that had already passed—the
Reviser receives explicit diagnostic feedback (check ID, reason, and verbatim evidence
quote) and performs surgical patches while keeping passing sections intact.
"""

import logging
from typing import Any, Dict, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.config import settings
from src.schemas import LessonAttempt, LessonState

logger = logging.getLogger(__name__)


class RevisionOutput(BaseModel):
    """Structured response from the Reviser LLM."""

    changes_made: str = Field(
        description="Concise summary naming each failed check and describing the exact targeted fix applied."
    )
    revised_lesson: str = Field(
        description="The complete revised lesson in Markdown with targeted surgical fixes applied. All passing sections must be preserved."
    )


def build_reviser_prompt(state: LessonState) -> str:
    """Construct diagnostic revision prompt with explicit check failures and quotes."""
    current_attempt = state.attempts[-1]
    eval_result = current_attempt.evaluation

    failures = []
    if eval_result:
        for c in eval_result.checks:
            if not c.passed:
                quote_part = (
                    f"\n  Evidence Quote: \"{c.evidence_quote}\""
                    if c.evidence_quote
                    else ""
                )
                failures.append(
                    f"- Check ID: {c.check_id}\n  Diagnostic Reason: {c.reason}{quote_part}"
                )

    failures_str = "\n".join(failures)

    prompt = f"""You are an expert pedagogical editor performing targeted surgical revisions on a lesson draft for a beginner student.

Target Learner: 12th-grade graduate from India, non-English-medium background, limited English vocabulary, zero technical background.

### CURRENT LESSON DRAFT:
\"\"\"
{current_attempt.content}
\"\"\"

### FAILED RUBRIC CHECKPOINTS (MUST FIX):
{failures_str}

### INSTRUCTIONS FOR SURGICAL REVISION:
1. Fix ONLY the failed checks listed above.
2. DO NOT rewrite the entire lesson from scratch. Preserve all sections that are already working well.
3. If `accuracy` failed: remove any claims that RAG retrains model weights, and clarify that the model remains frozen while external notes are fetched.
4. If `reading_level` failed: shorten long sentences into two or three crisp sentences (keep average words per sentence under 15). Use simple vocabulary.
5. If `jargon_defined` failed: make sure every technical term is clearly defined in simple words right when it is first used.
6. If `no_idioms` failed: replace idioms and slang with clear literal language.
7. If `worked_example` failed: add or refine a step-by-step example set in an Indian college context (e.g. exam notice PDF chatbot).
8. If `analogy` failed: add an intuitive everyday analogy (e.g. open-book exam vs closed-book test).
9. If `wrap_up` failed: ensure there is a clear summary and EXACTLY three numbered questions in the Self-Check section.

Return a JSON object containing:
- `changes_made`: A bulleted summary explicitly naming each failed check and explaining what surgical edits were made.
- `revised_lesson`: The full updated lesson in Markdown.
"""
    return prompt


def reviser_node(
    state: LessonState, client: Optional[genai.Client] = None
) -> Dict[str, Any]:
    """Execute surgical revision and record new attempt with changes_made summary."""
    next_attempt_num = state.current_attempt + 1
    logger.info(
        f"Executing Reviser Node (Producing Attempt {next_attempt_num}/{state.max_retries})..."
    )

    if client is None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your .env file or environment variables."
            )
        client = genai.Client(api_key=settings.gemini_api_key)

    prompt = build_reviser_prompt(state)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RevisionOutput,
        temperature=settings.generator_temperature,
    )

    response = client.models.generate_content(
        model=settings.generator_model,
        contents=prompt,
        config=config,
    )

    revision = RevisionOutput.model_validate_json(response.text)

    # Create new attempt record
    new_attempt = LessonAttempt(
        attempt_number=next_attempt_num,
        content=revision.revised_lesson.strip(),
        changes_made=revision.changes_made.strip(),
    )

    return {
        "attempts": state.attempts + [new_attempt],
        "current_attempt": next_attempt_num,
        "final_lesson": revision.revised_lesson.strip(),
    }
