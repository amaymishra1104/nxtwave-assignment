"""LLM Judge module for evaluating qualitative rubric checkpoints.

Executes a single structured LLM call per lesson (Amendment 7) returning all
qualitative and hybrid checks. Handles API retries, exponential backoff on 429/503,
and enforces verbatim evidence-quote verification (Amendment 1).
"""

import logging
import re
import time
from typing import Dict, List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field

from src.config import settings
from src.schemas import CheckResult, FactItem

logger = logging.getLogger(__name__)

LLM_CHECK_IDS = [
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


class LLMCheckItem(BaseModel):
    """Result for a single LLM-evaluated check."""

    check_id: str = Field(
        description="One of: accuracy, what_why_how, key_points, jargon_defined, no_idioms, worked_example, analogy, coherent_flow, wrap_up"
    )
    passed: bool = Field(description="Strict boolean pass or fail (no partial credit)")
    reason: str = Field(
        description="If passed, brief confirmation. If failed, actionable critique in format: [WHAT IS WRONG] + [WHERE] + [WHAT IS NEEDED]."
    )
    evidence_quote: str = Field(
        default="",
        description="Verbatim exact quote copied directly from the lesson text demonstrating violation. Leave empty string if a required element is entirely missing.",
    )


class LLMJudgeBatchResponse(BaseModel):
    """Unified response containing all LLM judge checks for a lesson (Amendment 7)."""

    checks: List[LLMCheckItem]


def normalize_ws(text: str) -> str:
    """Normalize internal whitespace and newlines for robust substring matching."""
    return " ".join(text.split())


def verify_evidence_quote(quote: str, lesson_text: str) -> bool:
    """Verify that a non-empty evidence quote exists verbatim in the lesson text.

    Normalizes whitespace only. Returns True for empty quotes (missing element failures).
    """
    clean_quote = quote.strip()
    if not clean_quote:
        # Amendment 1: Empty quotes are allowed for missing element failures
        return True

    # Check exact match
    if clean_quote in lesson_text:
        return True

    # Check whitespace-normalized match
    if normalize_ws(clean_quote) in normalize_ws(lesson_text):
        return True

    return False


def build_judge_prompt(
    lesson_text: str,
    fact_pack: List[FactItem],
    glossary: Optional[Dict[str, str]] = None,
    planner_checklist: Optional[List[str]] = None,
) -> str:
    """Construct the system prompt and instructions for the LLM judge."""
    facts_str = "\n".join(
        [
            f"- [{f.id}] ({f.category}): {f.fact} (Source: {f.source_name}, URL: {f.source_url})"
            for f in fact_pack
        ]
    )

    glossary_str = ""
    if glossary:
        glossary_str = "### GLOSSARY OF TECHNICAL TERMS:\n" + "\n".join(
            [f"- {k}: {v}" for k, v in glossary.items()]
        )

    checklist = planner_checklist or [
        "retrieval",
        "embeddings",
        "vector database",
        "chunking",
        "augmenting the prompt",
        "generation",
        "hallucination reduction",
        "limitations",
    ]
    checklist_str = "\n".join([f"- {item}" for item in checklist])

    prompt = f"""You are a strict, objective Pedagogical Grader evaluating a lesson titled "Introduction to RAG (Retrieval-Augmented Generation)".
Target Learner: 12th-grade graduate from India, non-English-medium schooling background, limited English vocabulary, zero technical knowledge, aspiring to start an AI career.

### INSTRUCTIONS:
1. Judge each check INDEPENDENTLY.
2. Apply the criteria LITERALLY. Fail when the criterion is not clearly and completely met.
3. NEVER award partial credit. It must be strictly true or false.
4. When a check fails, the `reason` MUST be actionable for the Reviser:
   Format: [WHAT IS WRONG] + [WHERE IT OCCURS] + [WHAT IS NEEDED TO FIX IT].
5. Evidence Quote Rule (Amendment 1):
   - If citing a text violation, `evidence_quote` MUST be copied VERBATIM from the lesson text (normalizing spaces only).
   - If a required element is completely MISSING, leave `evidence_quote` as an empty string `""`.
   - Never paraphrase or fabricate evidence quotes.

### GROUND TRUTH FACT PACK:
{facts_str}

{glossary_str}

### MANDATORY KEY CONCEPTS CHECKLIST:
{checklist_str}

### CHECKPOINTS TO EVALUATE:
1. `accuracy`:
   - pass=true only if ZERO statements contradict the Ground Truth Fact Pack.
   - Hard fail if the lesson claims the model must be retrained to add new documents (the lesson must clarify that at answer time, new documents can be added without retraining the model).
   - Hard fail if the lesson claims RAG completely stops, eliminates, or prevents all hallucinations or errors (fact pack fact_03 states RAG REDUCES hallucinations; it does not eliminate them).
2. `what_why_how`:
   - pass=true only if all three are explicitly and clearly answered: What RAG is, Why it matters / why LLMs fail without it, and How it works end-to-end.
3. `key_points`:
   - pass=true only if ALL 8 mandatory concepts from the checklist are explicitly covered.
4. `jargon_defined`:
   - pass=true only if every technical term used is explained simply and intuitively, without circular definitions.
5. `no_idioms`:
   - pass=true only if the lesson contains ZERO Western idioms, colloquialisms, or slang (e.g., 'silver bullet', 'bite the bullet', 'hit the ground running').
6. `worked_example`:
   - pass=true only if there is a concrete, step-by-step worked example familiar to an Indian student (e.g. college chatbot answering notice inquiries).
7. `analogy`:
   - pass=true only if there is at least one intuitive everyday analogy (e.g. open-book exam vs closed-book test).
8. `coherent_flow`:
   - pass=true only if concepts follow a logical learning progression (foundational concepts introduced before advanced combinations).
9. `wrap_up`:
   - pass=true only if the self-check questions test conceptual understanding without requiring prior technical knowledge.

### LESSON DRAFT:
\"\"\"
{lesson_text}
\"\"\"
"""
    return prompt


def call_gemini_with_backoff(
    client: genai.Client,
    model: str,
    prompt: str,
    schema: Optional[type[BaseModel]] = None,
    temperature: float = 0.2,
    max_api_retries: int = 3,
) -> str:
    """Call Gemini API with exponential backoff on 429/503 errors."""
    delay = 2.0
    last_exception = None

    for attempt in range(max_api_retries):
        try:
            if schema:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=temperature,
                )
            else:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text

        except APIError as e:
            last_exception = e
            status_code = getattr(e, "code", None)
            if status_code in (429, 503) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning(
                    f"Gemini API rate/availability limit ({status_code}). Backing off for {delay:.1f}s (Attempt {attempt+1}/{max_api_retries})"
                )
                time.sleep(delay)
                delay *= 2.0
            else:
                raise e
        except Exception as e:
            last_exception = e
            if "429" in str(e) or "503" in str(e):
                logger.warning(
                    f"Gemini transient error. Backing off for {delay:.1f}s (Attempt {attempt+1}/{max_api_retries})"
                )
                time.sleep(delay)
                delay *= 2.0
            else:
                raise e

    raise RuntimeError(
        f"Gemini API failed after {max_api_retries} attempts: {last_exception}"
    )


def run_llm_judge(
    lesson_text: str,
    fact_pack: List[FactItem],
    glossary: Optional[Dict[str, str]] = None,
    planner_checklist: Optional[List[str]] = None,
    client: Optional[genai.Client] = None,
    max_retries: int = 2,
) -> List[CheckResult]:
    """Execute the unified LLM judge call, validate schemas, and verify evidence quotes."""
    api_key = settings.gemini_api_key
    if client is None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your .env file or environment variables."
            )
        client = genai.Client(api_key=api_key)

    base_prompt = build_judge_prompt(
        lesson_text, fact_pack, glossary, planner_checklist
    )
    current_prompt = base_prompt

    for json_attempt in range(max_retries + 1):
        try:
            raw_json = call_gemini_with_backoff(
                client=client,
                model=settings.judge_model,
                prompt=current_prompt,
                schema=LLMJudgeBatchResponse,
                temperature=settings.judge_temperature,
            )

            parsed = LLMJudgeBatchResponse.model_validate_json(raw_json)

            # Check quotes
            results: List[CheckResult] = []
            quote_mismatches = []

            for item in parsed.checks:
                if not item.passed and item.evidence_quote.strip():
                    is_valid = verify_evidence_quote(item.evidence_quote, lesson_text)
                    if not is_valid:
                        quote_mismatches.append(
                            (item.check_id, item.evidence_quote, item.reason)
                        )
                        continue

                results.append(
                    CheckResult(
                        check_id=item.check_id,
                        passed=item.passed,
                        reason=item.reason,
                        evidence_quote=item.evidence_quote.strip(),
                    )
                )

            # If there are quote mismatches, retry the judge once per user instructions
            if quote_mismatches:
                if json_attempt < 1:  # Retry judge once for quote mismatch
                    logger.warning(
                        f"Evidence quote mismatch detected: {quote_mismatches}. Retrying judge once..."
                    )
                    error_details = "\n".join(
                        [
                            f"- Check '{cid}': quote '{q}' was NOT found verbatim in the lesson draft. Copy the exact substring or leave empty string if missing."
                            for cid, q, _ in quote_mismatches
                        ]
                    )
                    current_prompt = (
                        base_prompt
                        + f"\n\nERROR IN PREVIOUS RESPONSE: The following quotes were not found verbatim:\n{error_details}"
                    )
                    continue
                else:
                    # After 1 retry, mark failing checks as judge_error (counts as fail, logged)
                    for cid, q, orig_reason in quote_mismatches:
                        results.append(
                            CheckResult(
                                check_id=cid,
                                passed=False,
                                reason=f"JUDGE_ERROR: Evidence quote was not found verbatim in lesson text (Judge cited: '{q}'). {orig_reason}",
                                evidence_quote="",
                            )
                        )

            return results

        except Exception as e:
            logger.warning(
                f"LLM Judge attempt {json_attempt + 1} encountered error: {e}"
            )
            if json_attempt >= max_retries:
                # Fallback reporting judge execution failure
                return [
                    CheckResult(
                        check_id=cid,
                        passed=False,
                        reason=f"JUDGE_ERROR: Execution failed after {max_retries} attempts: {str(e)}",
                        evidence_quote="",
                    )
                    for cid in LLM_CHECK_IDS
                ]

    return []
