"""Generator Node: Drafts the standalone Markdown lesson.

WHY THIS NODE EXISTS:
Transforms the factual grounding, outline, and learner constraints into accessible,
pedagogically sound instructional text (~800-1200 words). Incorporates active rules
learned from historical memory to continuously improve draft quality.
"""

import logging
from typing import Any, Dict, Optional
from google import genai
from google.genai import types

from src.checks.llm_judge import call_gemini_with_backoff
from src.config import settings
from src.schemas import LessonAttempt, LessonState

logger = logging.getLogger(__name__)


def build_generator_prompt(state: LessonState) -> str:
    """Build pedagogical drafting prompt adhering strictly to plain requirements without leaking test thresholds."""
    plan = state.plan
    outline_str = "\n".join([f"- {s}" for s in (plan.outline if plan else [])])
    concepts_str = ", ".join(
        (
            plan.key_concepts
            if plan
            else [
                "retrieval",
                "embeddings",
                "vector database",
                "chunking",
                "augmenting the prompt",
                "generation",
                "hallucination reduction",
                "limitations",
            ]
        )
    )

    facts_str = "\n".join([f"- {f.fact}" for f in state.fact_pack])

    rules_str = ""
    if state.learned_rules:
        rules_str = (
            "### LEARNED TEACHING RULES FROM PREVIOUS RUNS:\n"
            + "\n".join([f"- {rule}" for rule in state.learned_rules])
            + "\n\n"
        )

    prompt = f"""You are a master educator crafting an introductory lesson on "{state.topic}".

### TARGET LEARNER PERSONA:
- 12th-grade high school graduate from India.
- Non-English-medium schooling background.
- Limited English vocabulary; struggles with long complex sentences and abstract definitions.
- Zero prior computer programming or AI experience.
- Aspires to start an AI career and needs clear mental models.

### PEDAGOGICAL REQUIREMENTS:
1. Tone & Style Rules (CRITICAL FOR BEGINNER ACCESSIBILITY):
   - One idea per sentence: Express only one single thought per sentence. Never pack multiple concepts, actions, or steps into one sentence.
   - Short sentences: Keep sentences short, crisp, and direct. Use full stops often.
   - Everyday words: Use simple, familiar high-school words. Avoid complex, formal, or multi-syllable vocabulary (e.g. use "college office" instead of "university administration", "check" instead of "verification", "math numbers" instead of "mathematical calculations", "standard" instead of "traditional").
   - No long chains of clauses: Never connect multiple ideas using conjunctions like "and", "which", "while", "whereas", or "consequently". Break them into separate standalone sentences.
   - Explain each new term in a short separate sentence: When you first introduce any new technical term, immediately follow it with a short, standalone sentence that explains what it means in plain words before continuing.
   - Beginner-friendly language: Never use Western idioms, colloquialisms, or buzzwords (e.g., avoid "bite the bullet", "hit the ground running", "silver bullet").
2. Core Content:
   - Thoroughly explain: (1) What RAG is, (2) Why standard AI models need it (knowledge limits and hallucinations), and (3) How it works.
   - Explain all of these essential concepts: {concepts_str}.
   - Never state or imply that RAG retrains, fine-tunes, or modifies the model's neural network weights.
3. Teaching Tools:
   - Use an intuitive everyday analogy (e.g. taking an open-book exam with textbooks vs a closed-book memory test).
   - Walk through a concrete step-by-step worked example familiar in India (e.g. a college student asking an admission chatbot about an exam notice PDF circular).
   - Define every technical term in plain words right when you first introduce it before using it again.
4. Structure:
   - Use clean Markdown with clear headings (# and ##).
   - Include a dedicated section with heading '## Worked Example' (e.g. ## Worked Example: College Admission Chatbot).
   - Include a concise Summary section at the end.
   - Conclude with a "Self-Check Questions" section containing EXACTLY three numbered questions testing understanding.
5. Target Length: Approximately 800 to 1200 words.

{rules_str}### VERIFIED FACTS TO GROUND YOUR WRITING:
{facts_str}

### LESSON OUTLINE:
{outline_str}

Now write the complete, standalone beginner lesson in Markdown:
"""
    return prompt


def generator_node(
    state: LessonState, client: Optional[genai.Client] = None
) -> Dict[str, Any]:
    """Generate the lesson draft, apply any requested fault injection on attempt 0, and record attempt."""
    logger.info(f"Executing Generator Node (Attempt {state.current_attempt})...")

    if client is None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your .env file or environment variables."
            )
        client = genai.Client(api_key=settings.gemini_api_key)

    prompt = build_generator_prompt(state)

    lesson_text = call_gemini_with_backoff(
        client=client,
        model=settings.generator_model,
        prompt=prompt,
        schema=None,
        temperature=settings.generator_temperature,
    ).strip()

    # Optional Fault Injection hook on Attempt 0 for live demonstration (Amendment 5)
    injected_fault = None
    if state.fault_to_inject and state.current_attempt == 0:
        from src.fault_injector import inject_fault

        lesson_text = inject_fault(
            lesson_text=lesson_text,
            fault_type=state.fault_to_inject,
            client=client,
        )
        injected_fault = state.fault_to_inject
        logger.info(f"Deliberately injected fault '{injected_fault}' into Attempt 0.")

    # Create new attempt record
    attempt = LessonAttempt(
        attempt_number=state.current_attempt,
        content=lesson_text,
        fault_injected=injected_fault,
    )

    return {
        "attempts": state.attempts + [attempt],
        "final_lesson": lesson_text,
    }

