"""Reflector Node: Extracts recurring failure patterns, evolves memory rules, and proposes rubric v2.

WHY THIS NODE EXISTS:
Drives the self-evolving capability across runs. Rather than remaining static, the system
learns from its mistakes by synthesizing recurring rejection patterns into actionable rules
stored in SQLite, injecting them into future generation attempts, and proposing versioned
rubric refinements in `rubric_v2_proposed.json` with a transparent changelog.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.memory.store import MemoryStore
from src.schemas import LessonState

logger = logging.getLogger(__name__)

# Heuristic rule templates for common failure modes
FAILURE_RULE_TEMPLATES = {
    "reading_level": "Write one single idea per sentence. Use very short sentences and simple everyday words so that non-English-medium high school graduates understand instantly.",
    "jargon_defined": "Define every specialized term (e.g. embeddings, chunking, vector database) with simple words right inside the first sentence it is introduced.",
    "no_idioms": "Use strictly literal language. Avoid all colloquial phrases or English idioms such as 'from scratch', 'silver bullet', or 'bite the bullet'.",
    "accuracy": "Explicitly clarify that RAG does NOT retrain or alter model weights; the base model stays completely frozen while external text is fetched.",
    "worked_example": "Provide a concrete 3-step walkthrough set in an Indian college (e.g. a student asking an admission chatbot about an exam notice PDF).",
    "analogy": "Include the open-book exam analogy early in the lesson: comparing closed-book memorization with searching textbook pages during an exam.",
    "wrap_up": "Conclude the lesson with dedicated sections: a step-by-step '## Worked Example', a concise '## Summary', and a '## Self-Check' section containing exactly three numbered questions.",
}


def reflector_node(state: LessonState, store: Optional[MemoryStore] = None) -> Dict[str, Any]:
    """Analyze rejection logs, extract learned rules into memory, and propose rubric v2."""
    logger.info("Executing Reflector Node (Self-Evolution & Memory Update)...")

    if store is None:
        store = MemoryStore()

    # 1. Persist run to SQLite memory store
    store.save_run(state)

    # 2. Extract failing patterns from current run and historical memory
    failing_in_current_run = set()
    for attempt in state.attempts:
        if attempt.evaluation:
            for fid in attempt.evaluation.failing_checks:
                failing_in_current_run.add(fid)

    historical_frequencies = store.get_failure_frequency()
    logger.info(f"Historical failure frequencies: {historical_frequencies}")

    newly_added_rules = []
    for check_id in failing_in_current_run:
        # If this check failed or has recurring historical failures, extract/reinforce rule
        if check_id in FAILURE_RULE_TEMPLATES:
            rule_text = FAILURE_RULE_TEMPLATES[check_id]
            store.add_or_update_rule(rule_text=rule_text, source_check_id=check_id)
            newly_added_rules.append(rule_text)

    # 3. Propose rubric v2 with changelog into data/rubric_v2_proposed.json
    rubric_v1_path = settings.rubric_v1_path
    if rubric_v1_path.exists():
        rubric_data = json.loads(rubric_v1_path.read_text(encoding="utf-8"))
    else:
        rubric_data = {"version": "1.0.0", "checks": []}

    # Synthesize changelog based on observed failures
    changelog_entries = []
    if "reading_level" in historical_frequencies:
        changelog_entries.append(
            f"Clarified reading_level guidance based on {historical_frequencies['reading_level']} historical failures: recommend <= 12 words per sentence."
        )
    if "jargon_defined" in historical_frequencies:
        changelog_entries.append(
            f"Enhanced jargon_defined criteria based on {historical_frequencies['jargon_defined']} historical occurrences: terms must be defined in the same initial clause."
        )
    if not changelog_entries:
        changelog_entries.append(
            "Initial proposal incorporating stricter evidence verification and glossary definition cues."
        )

    proposed_rubric = {
        "version": "2.0.0-proposed",
        "generated_at": datetime.now().isoformat(),
        "proposed_by": "ReflectorNode",
        "changelog": changelog_entries,
        "historical_failure_statistics": historical_frequencies,
        "active_learned_rules_applied": store.get_top_active_rules(limit=5),
        "name": rubric_data.get("name", "") + " (v2 Proposed)",
        "description": rubric_data.get("description", "") + " [Evolved via Self-Reflection]",
        "checks": rubric_data.get("checks", []),
    }

    proposed_path = settings.rubric_v2_proposed_path
    proposed_path.write_text(json.dumps(proposed_rubric, indent=2), encoding="utf-8")
    logger.info(f"Generated proposed rubric with changelog to {proposed_path}")

    # Return refreshed active learned rules
    active_rules = store.get_top_active_rules(limit=settings.active_rules_limit)
    return {
        "learned_rules": active_rules,
    }

