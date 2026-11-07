"""SQLite Persistent Memory Store for Lesson Agent (M5).

Persists runs, attempts, check_results, and self-evolved learned_rules across runs.
Supports rule deduplication and capping active rules at 5 (Amendment 9).
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config import settings
from src.schemas import CheckResult, LearnedRule, LessonAttempt, LessonState

logger = logging.getLogger(__name__)


class MemoryStore:
    """SQLite-backed memory store managing persistence and self-evolution telemetry."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema if tables do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Runs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    final_passed INTEGER NOT NULL,
                    fault_injected INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Ensure column exists if table was previously created without it
            try:
                cursor.execute("ALTER TABLE runs ADD COLUMN fault_injected INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists

            # Attempts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    lesson_text TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    failing_checks TEXT,
                    changes_made TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
                """
            )

            # Check results table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS check_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    check_id TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    reason TEXT,
                    evidence_quote TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (attempt_id) REFERENCES attempts (id),
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
                """
            )

            # Learned rules table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_text TEXT NOT NULL UNIQUE,
                    source_check_id TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_run(self, state: LessonState):
        """Save complete run telemetry, attempts, and individual check results."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            best_attempt = state.get_best_attempt()
            final_passed = 1 if (best_attempt and best_attempt.evaluation and best_attempt.evaluation.passed) else 0

            # 1. Upsert run
            fault_flag = 1 if (getattr(state, "fault_to_inject", None) is not None) else 0
            cursor.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, topic, status, attempt_count, final_passed, fault_injected, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.run_id,
                    state.topic,
                    state.status,
                    len(state.attempts),
                    final_passed,
                    fault_flag,
                    datetime.now().isoformat(),
                ),
            )

            # 2. Insert attempts and check results
            for attempt in state.attempts:
                failing_str = (
                    ",".join(attempt.evaluation.failing_checks)
                    if attempt.evaluation
                    else ""
                )
                attempt_passed = (
                    1 if (attempt.evaluation and attempt.evaluation.passed) else 0
                )

                cursor.execute(
                    """
                    INSERT INTO attempts (run_id, attempt_number, lesson_text, passed, failing_checks, changes_made, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state.run_id,
                        attempt.attempt_number,
                        attempt.content,
                        attempt_passed,
                        failing_str,
                        attempt.changes_made or "",
                        attempt.timestamp.isoformat(),
                    ),
                )
                attempt_id = cursor.lastrowid

                if attempt.evaluation:
                    for check in attempt.evaluation.checks:
                        cursor.execute(
                            """
                            INSERT INTO check_results (attempt_id, run_id, check_id, passed, reason, evidence_quote, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                attempt_id,
                                state.run_id,
                                check.check_id,
                                1 if check.passed else 0,
                                check.reason,
                                check.evidence_quote,
                                datetime.now().isoformat(),
                            ),
                        )
            conn.commit()
            logger.info(f"Persisted run '{state.run_id}' to SQLite database.")

    def add_or_update_rule(self, rule_text: str, source_check_id: str) -> bool:
        """Add a new learned rule or increment frequency count if already known.

        Enforces deduplication and manages active rules cap at 5 (Amendment 9).
        """
        clean_rule = rule_text.strip()
        if not clean_rule:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, failure_count FROM learned_rules WHERE LOWER(rule_text) = LOWER(?)",
                (clean_rule,),
            )
            row = cursor.fetchone()

            if row:
                new_count = row["failure_count"] + 1
                cursor.execute(
                    "UPDATE learned_rules SET failure_count = ?, active = 1 WHERE id = ?",
                    (new_count, row["id"]),
                )
                logger.info(f"Updated recurring rule #{row['id']}: count={new_count}")
            else:
                cursor.execute(
                    """
                    INSERT INTO learned_rules (rule_text, source_check_id, failure_count, active, created_at)
                    VALUES (?, ?, 1, 1, ?)
                    """,
                    (clean_rule, source_check_id, datetime.now().isoformat()),
                )
                logger.info(f"Added new learned rule for check '{source_check_id}': '{clean_rule}'")

            conn.commit()

        # Enforce active rules limit of 5 (keep top 5 by failure_count)
        self.enforce_active_rules_limit(limit=settings.active_rules_limit)
        return True

    def enforce_active_rules_limit(self, limit: int = 5):
        """Cap the top active rules at `limit`, deactivating lower-ranked rules."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deactivate all
            cursor.execute("UPDATE learned_rules SET active = 0")
            # Activate top N by failure_count DESC, id DESC
            cursor.execute(
                f"""
                UPDATE learned_rules SET active = 1
                WHERE id IN (
                    SELECT id FROM learned_rules
                    ORDER BY failure_count DESC, id DESC
                    LIMIT {limit}
                )
                """
            )
            conn.commit()

    def get_top_active_rules(self, limit: int = 5) -> List[str]:
        """Fetch the top active learned rules to inject into the Generator prompt."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rule_text FROM learned_rules
                WHERE active = 1
                ORDER BY failure_count DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [r["rule_text"] for r in rows]

    def get_failure_frequency(self) -> Dict[str, int]:
        """Get total historical failure count per check ID across natural (non-injected) runs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cr.check_id, COUNT(*) as fail_count
                FROM check_results cr
                JOIN runs r ON cr.run_id = r.run_id
                WHERE cr.passed = 0 AND r.fault_injected = 0
                GROUP BY cr.check_id
                ORDER BY fail_count DESC
                """
            )
            rows = cursor.fetchall()
            return {r["check_id"]: r["fail_count"] for r in rows}

