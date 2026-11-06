"""Planner Node: Synthesizes must-cover checklist and pedagogical outline.

WHY THIS NODE EXISTS:
Prevents generation gaps and erratic flow. By producing a structured plan covering
the core What/Why/How pillars and the 8 mandatory technical concepts before any prose
is written, it guarantees that the Generator has an explicit blueprint aligned with
the Indian beginner learner persona.
"""

import logging
from typing import Any, Dict, Optional
from google import genai
from google.genai import types

from src.config import settings
from src.schemas import LessonPlan, LessonState

logger = logging.getLogger(__name__)

MANDATORY_CONCEPTS = [
    "retrieval",
    "embeddings",
    "vector database",
    "chunking",
    "augmenting the prompt",
    "generation",
    "hallucination reduction",
    "limitations",
]


def planner_node(
    state: LessonState, client: Optional[genai.Client] = None
) -> Dict[str, Any]:
    """Produce a structured lesson plan covering what/why/how and the 8 core concepts."""
    logger.info("Executing Planner Node...")

    if client is None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your .env file or environment variables."
            )
        client = genai.Client(api_key=settings.gemini_api_key)

    facts_summary = "\n".join([f"- {f.id}: {f.fact}" for f in state.fact_pack[:6]])

    prompt = f"""You are an expert curriculum designer creating a lesson plan for:
Topic: "{state.topic}"
Target Learner: 12th-grade graduate from India, non-English-medium background, limited English vocabulary, zero technical background, wants to start an AI career.

Produce a structured lesson plan that covers:
1. What RAG is, Why it matters (why LLMs make mistakes/hallucinate without it), and How it works.
2. The 8 mandatory concepts: {', '.join(MANDATORY_CONCEPTS)}.
3. An India-relevant scenario (e.g. college chatbot answering notice circular questions).
4. An everyday analogy (e.g. open-book exam vs closed-book test).
5. A logical outline with simple headings.

Verified Facts reference:
{facts_summary}
"""

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=LessonPlan,
        temperature=settings.judge_temperature,
    )

    response = client.models.generate_content(
        model=settings.generator_model,
        contents=prompt,
        config=config,
    )

    plan = LessonPlan.model_validate_json(response.text)
    return {"plan": plan}
