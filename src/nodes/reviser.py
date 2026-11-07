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

from src.checks.llm_judge import call_gemini_with_backoff
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
3. If `accuracy` failed: clarify that at answer time, new documents can be added without retraining the model. Also ensure any claim about hallucinations states that RAG reduces hallucinations rather than completely stopping or eliminating them.
4. If `reading_level` failed:
   - Carefully review the measured metrics, the exact sentences over 15 words quoted in the diagnostic reason, and the listed multi-syllable non-glossary words.
   - Fix reading_level by splitting each of those specific long sentences into 2 or 3 short, punchy sentences (keep each sentence under 12-14 words).
   - Swap the identified multi-syllable non-glossary words for simple 1-syllable or 2-syllable everyday words (e.g. use "college office" instead of "university administration", "check" instead of "verification", "math numbers" instead of "mathematical calculations", "standard" instead of "traditional", "so" instead of "consequently").
   - Leave all passing sections completely unchanged.
5. If `jargon_defined` failed: make sure every technical term is clearly defined in simple words right when it is first used. If terms like "high-dimensional", "indexes", or "similarity search" appear, replace them with plain words (e.g., "organizes for quick lookup", "finding chunks with matching ideas") or define them immediately in plain words.
6. If `no_idioms` failed: replace idioms and slang with clear literal language.
7. If `worked_example` failed: add or refine a step-by-step example set in an Indian college context (e.g. exam notice PDF chatbot).
8. If `analogy` failed: add an intuitive everyday analogy (e.g. open-book exam vs closed-book test).
9. If `wrap_up` failed:
   - Ensure the lesson has a dedicated section with heading '## Worked Example'.
   - Ensure there is a concise '## Summary' section.
   - Ensure the lesson concludes with a '## Self-Check' section containing EXACTLY three numbered questions (1., 2., 3.).

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

    raw_json = call_gemini_with_backoff(
        client=client,
        model=settings.generator_model,
        prompt=prompt,
        schema=RevisionOutput,
        temperature=settings.generator_temperature,
    )

    revision = RevisionOutput.model_validate_json(raw_json)

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

