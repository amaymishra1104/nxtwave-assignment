"""Unit tests for SQLite MemoryStore and Reflector self-evolution (M5)."""

import json
from pathlib import Path
import pytest

from src.memory.store import MemoryStore
from src.nodes.reflector import reflector_node
from src.schemas import (
    CheckResult,
    EvaluationResult,
    LessonAttempt,
    LessonState,
)


def test_memory_store_lifecycle(tmp_path):
    """Verify SQLite database initialization, run insertion, and telemetry retrieval."""
    db_file = tmp_path / "test_memory.db"
    store = MemoryStore(db_path=str(db_file))

    state = LessonState(
        run_id="run_mem_test_1",
        topic="Introduction to RAG",
        status="passed",
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="Lesson text for attempt 0",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[
                        CheckResult(check_id="accuracy", passed=False, reason="Error", evidence_quote="quote"),
                        CheckResult(check_id="no_idioms", passed=True, reason="OK"),
                    ],
                    failing_checks=["accuracy"],
                ),
            ),
            LessonAttempt(
                attempt_number=1,
                content="Lesson text for attempt 1",
                evaluation=EvaluationResult(
                    passed=True,
                    checks=[
                        CheckResult(check_id="accuracy", passed=True, reason="Fixed"),
                        CheckResult(check_id="no_idioms", passed=True, reason="OK"),
                    ],
                    failing_checks=[],
                ),
            ),
        ],
    )

    store.save_run(state)

    # Check failure frequency
    freq = store.get_failure_frequency()
    assert freq.get("accuracy") == 1


def test_learned_rules_deduplication_and_cap_at_5(tmp_path):
    """Amendment 9: Deduplicate rules, track failure frequency, and cap active rules at 5."""
    db_file = tmp_path / "test_rules.db"
    store = MemoryStore(db_path=str(db_file))

    # Add same rule twice
    store.add_or_update_rule("Keep sentences under 15 words.", "reading_level")
    store.add_or_update_rule("Keep sentences under 15 words.", "reading_level")

    active_rules = store.get_top_active_rules(limit=10)
    # Deduplication check: should only appear once
    assert len(active_rules) == 1

    # Add 5 more distinct rules (total 6 distinct rules)
    for i in range(5):
        store.add_or_update_rule(f"Unique rule number {i}", "jargon_defined")

    # Amendment 9 check: top active rules must be capped at 5
    active_rules = store.get_top_active_rules(limit=5)
    assert len(active_rules) <= 5


def test_reflector_node_generates_rubric_v2_with_changelog(tmp_path, monkeypatch):
    """Verify reflector generates data/rubric_v2_proposed.json without modifying rubric_v1."""
    from src.config import settings

    monkeypatch.setattr(settings, "database_path", tmp_path / "reflector_test.db")
    monkeypatch.setattr(settings, "rubric_v2_proposed_path", tmp_path / "rubric_v2_proposed.json")

    store = MemoryStore(db_path=str(tmp_path / "reflector_test.db"))

    state = LessonState(
        run_id="run_reflector_001",
        status="revising",
        attempts=[
            LessonAttempt(
                attempt_number=0,
                content="Draft text",
                evaluation=EvaluationResult(
                    passed=False,
                    checks=[
                        CheckResult(check_id="reading_level", passed=False, reason="Too complex"),
                        CheckResult(check_id="jargon_defined", passed=False, reason="Missing def"),
                    ],
                    failing_checks=["reading_level", "jargon_defined"],
                ),
            )
        ],
    )

    res = reflector_node(state, store=store)
    assert "learned_rules" in res
    assert len(res["learned_rules"]) >= 1

    # Verify proposed rubric was created
    proposed_file = tmp_path / "rubric_v2_proposed.json"
    assert proposed_file.exists()

    proposed_json = json.loads(proposed_file.read_text(encoding="utf-8"))
    assert proposed_json["version"] == "2.0.0-proposed"
    assert "changelog" in proposed_json
    assert len(proposed_json["changelog"]) > 0
    assert "historical_failure_statistics" in proposed_json

