"""Grounder Node: Loads verified domain truth, glossary, and active memory rules.

WHY THIS NODE EXISTS:
Decouples domain knowledge from model weights. By injecting verified facts from the
Lewis et al. (2020) NeurIPS paper and official documentation into state before planning
or drafting, it establishes an immutable factual anchor for generation and accuracy grading.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from src.config import settings
from src.schemas import FactItem, LessonState

logger = logging.getLogger(__name__)


def grounder_node(state: LessonState) -> Dict[str, Any]:
    """Load fact pack, glossary, and active memory rules into pipeline state."""
    logger.info("Executing Grounder Node...")

    # Load fact pack
    fact_pack_path = settings.fact_pack_path
    facts = []
    if fact_pack_path.exists():
        raw_facts = json.loads(fact_pack_path.read_text(encoding="utf-8"))
        facts = [FactItem(**item) for item in raw_facts]
    else:
        logger.warning(f"Fact pack not found at {fact_pack_path}")

    # Load glossary
    glossary_path = settings.glossary_path
    glossary = {}
    if glossary_path.exists():
        glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
    else:
        logger.warning(f"Glossary not found at {glossary_path}")

    # Load learned rules from memory store if database exists
    rules = []
    try:
        from src.memory.store import MemoryStore

        store = MemoryStore(db_path=str(settings.database_path))
        rules = store.get_top_active_rules(limit=settings.active_rules_limit)
    except Exception as e:
        logger.debug(f"Memory store not initialized yet or empty: {e}")

    return {
        "fact_pack": facts,
        "glossary": glossary,
        "learned_rules": rules,
    }
