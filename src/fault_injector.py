"""Fault Injection module for live evaluator demonstrations (M6).

Supports:
- hallucination: Deterministic insertion claiming RAG retrains model weights
- no_example: Deterministic stripping of the worked example section
- no_quiz: Deterministic stripping of the self-check questions section
- jargon: Injects undefined complex mathematical terms
- long_sentences: Replaces paragraphs with 35+ word compound run-on sentences
"""

import logging
import re
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)

HALLUCINATION_TEXT = (
    "\n\n**Important Technical Detail:** RAG works by continuously retraining, updating, and fine-tuning "
    "the underlying neural network weights of the language model directly on your private document collection.\n\n"
)

JARGON_TEXT = (
    "\n\nDuring indexing, the system maps textual tokens onto a high-dimensional non-Euclidean manifold "
    "using anisotropic projection matrices and cosine similarity over dense latent subspaces.\n\n"
)

LONG_SENTENCES_TEXT = (
    "\n\nWhen an artificial intelligence system encounters a complex knowledge-intensive inquiry from an external human user, "
    "it systematically coordinates an extensive algorithmic search across multi-dimensional vector databases containing dense "
    "semantic embeddings of partitioned document collections before recursively synthesizing an elaborate natural language response "
    "that incorporates contextual provenance to satisfy the inquiry.\n\n"
)


def inject_fault(
    lesson_text: str,
    fault_type: str,
    client: Optional[genai.Client] = None,
) -> str:
    """Deliberately corrupt lesson draft to demonstrate live evaluator detection.

    Amendment 5: Deterministic code for hallucination, no_example, and no_quiz.
    """
    fault = fault_type.lower().strip()
    logger.info(f"Injecting fault '{fault}' into lesson draft...")

    if fault == "hallucination":
        # Deterministic insertion into the introduction/definition section
        if "## 2. What is RAG" in lesson_text:
            return lesson_text.replace(
                "## 2. What is RAG", f"## 2. What is RAG\n{HALLUCINATION_TEXT}"
            )
        return HALLUCINATION_TEXT + lesson_text

    elif fault == "no_example":
        # Deterministic regex stripping of the Worked Example section
        stripped = re.sub(
            r"(?i)##+\s*(?:\d+[\.\)]\s*)?(?:worked example|real-world example)[^\n]*[\s\S]*?(?=\n##+|\Z)",
            "",
            lesson_text,
        )
        return stripped.strip()

    elif fault == "no_quiz":
        # Deterministic regex stripping of the Self-Check Questions section
        stripped = re.sub(
            r"(?i)##+\s*(?:\d+[\.\)]\s*)?(?:self[- ]check|quiz|test your knowledge|check your understanding)[^\n]*[\s\S]*?(?=\n##+|\Z)",
            "",
            lesson_text,
        )
        return stripped.strip()

    elif fault == "jargon":
        # Injects undefined technical jargon
        if "### Step B" in lesson_text:
            return lesson_text.replace("### Step B", f"### Step B\n{JARGON_TEXT}")
        return lesson_text + JARGON_TEXT

    elif fault == "long_sentences":
        # Injects 40+ word compound academic sentences
        return lesson_text + LONG_SENTENCES_TEXT

    else:
        logger.warning(f"Unknown fault type '{fault_type}'; no fault injected.")
        return lesson_text
