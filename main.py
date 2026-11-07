"""Main entrypoint for the Lesson Agent system."""

import argparse
import logging
import sys
from pathlib import Path

from src.config import settings
from src.graph import build_lesson_graph, save_run_outputs
from src.schemas import LessonState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Lesson Content Generator & Evaluator"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Introduction to RAG (Retrieval-Augmented Generation)",
        help="Lesson topic to generate",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=settings.max_retries,
        help="Maximum number of revision retries before shipping best attempt",
    )
    parser.add_argument(
        "--inject-fault",
        type=str,
        choices=[
            "hallucination",
            "jargon",
            "no_example",
            "long_sentences",
            "no_quiz",
        ],
        default=None,
        help="Deliberately inject a fault into attempt 0 to test evaluator live",
    )
    parser.add_argument(
        "--demo-evolution",
        action="store_true",
        help="Run 3 iterations to demonstrate memory rule learning and application",
    )
    parser.add_argument(
        "--replay",
        type=str,
        default=None,
        help="Re-render Rich CLI presentation for a saved run ID (or 'latest') without making API calls",
    )
    parser.add_argument(
        "--browser",
        "--open",
        action="store_true",
        help="Open interactive visual dashboard in web browser upon completion",
    )

    args = parser.parse_args()

    if args.replay:
        from src.ui import replay_saved_run
        replay_saved_run(args.replay)
        return

    from src.ui import render_banner, render_attempt_grid, render_final_card
    render_banner(
        topic=args.topic,
        max_retries=args.max_retries,
        fault_hook=args.inject_fault,
        generator_model=settings.generator_model,
        judge_model=settings.judge_model,
    )

    graph = build_lesson_graph()

    if args.demo_evolution:
        print("\n>>> DEMO EVOLUTION MODE ACTIVATED (5 Iterations) <<<")
        print("Running 5 sequential iterations to demonstrate rule synthesis, persistence, and prompt injection.\n")

        from src.memory.store import MemoryStore
        store = MemoryStore()
        history = []

        total_iterations = 5
        for iteration in range(1, total_iterations + 1):
            print(f"\n=======================================================")
            print(f"            EVOLUTION RUN {iteration} OF {total_iterations}")
            print(f"=======================================================")

            # Check rules before run
            active_rules_before = store.get_top_active_rules(limit=5)
            print(f"[Run {iteration}] Active Rules Loaded from Memory ({len(active_rules_before)}):")
            for idx, r in enumerate(active_rules_before, 1):
                print(f"  {idx}. {r}")
            if not active_rules_before:
                print("  (None yet - cold start)")

            if iteration > 1:
                print(f"\n[Run {iteration}] Exact Rules Injected into Generator Prompt:")
                for idx, r in enumerate(active_rules_before, 1):
                    print(f"    • {r}")

            state = LessonState(
                topic=args.topic,
                max_retries=args.max_retries,
                fault_to_inject=None,
            )

            final_state_dict = graph.invoke(state)
            final_state = LessonState(**final_state_dict) if isinstance(final_state_dict, dict) else final_state_dict
            save_run_outputs(final_state)

            # Inspect SQLite table
            import sqlite3
            conn = sqlite3.connect(store.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, source_check_id, failure_count, active, rule_text FROM learned_rules ORDER BY failure_count DESC, id ASC")
            db_rows = cursor.fetchall()
            conn.close()

            print(f"\n[Run {iteration} Finished] SQLite `learned_rules` Table ({len(db_rows)} rows):")
            for row in db_rows:
                active_flag = "ACTIVE" if row[3] else "INACTIVE"
                print(f"  [ID {row[0]}] Check: {row[1]:<15} | Count: {row[2]} | {active_flag:<8} | Rule: {row[4][:65]}...")

            att0 = final_state.attempts[0] if final_state.attempts else None
            att0_fails = att0.evaluation.failing_checks if (att0 and att0.evaluation) else []
            history.append((iteration, att0_fails))
            print(f"  Attempt 0 Status: {'PASSED' if not att0_fails else f'FAILED ({len(att0_fails)} failing: {att0_fails})'}")
            print(f"  Total Attempts:   {len(final_state.attempts)}")
            print(f"  Final Verdict:    {final_state.status.upper()}")

        print("\n=======================================================")
        print("        DEMO EVOLUTION SUMMARY (ATTEMPT-0 PROGRESSION)")
        print("=======================================================")
        for it, fails in history:
            status_text = "PASSED (0 fails)" if not fails else f"FAILED ({len(fails)} failing: {fails})"
            print(f"  Iteration {it}: Attempt 0 -> {status_text}")
        print(f"\nActive Rules Capped at 5 (Deduplicated)")
        print(f"Proposed Rubric: {settings.rubric_v2_proposed_path}")
        print("=======================================================\n")
        return

    initial_state = LessonState(
        topic=args.topic,
        max_retries=args.max_retries,
        fault_to_inject=args.inject_fault,
    )

    logger.info("Starting autonomous LangGraph execution...")
    try:
        final_state_dict = graph.invoke(initial_state)
        # Reconstruct LessonState model from dictionary if returned as dict
        if isinstance(final_state_dict, dict):
            final_state = LessonState(**final_state_dict)
        else:
            final_state = final_state_dict

        # Save all output files
        lesson_file = save_run_outputs(final_state)

        # Render visual Rich UI
        best_attempt = final_state.get_best_attempt()
        best_num = best_attempt.attempt_number if best_attempt else 0
        fewest_fails = len(best_attempt.evaluation.failing_checks) if (best_attempt and best_attempt.evaluation) else 0

        for a in final_state.attempts:
            checks_list = [c.model_dump() for c in (a.evaluation.checks if a.evaluation else [])]
            failing_list = a.evaluation.failing_checks if a.evaluation else []
            render_attempt_grid(
                attempt_num=a.attempt_number,
                total_attempts=len(final_state.attempts),
                checks=checks_list,
                failing_checks=failing_list,
                changes_made=a.changes_made,
            )

        render_final_card(
            run_id=final_state.run_id,
            status=final_state.status,
            attempts_count=len(final_state.attempts),
            best_attempt_num=best_num,
            failing_count=fewest_fails,
            lesson_path=lesson_file,
        )

        if args.browser:
            from src.browser_view import open_dashboard_in_browser
            open_dashboard_in_browser(run_id=final_state.run_id)

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

