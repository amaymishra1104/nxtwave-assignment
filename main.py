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

    args = parser.parse_args()

    print("\n=======================================================")
    print("   GENAI CONTENT SYSTEMS: LESSON GENERATOR & EVALUATOR ")
    print("=======================================================")
    print(f"Topic:       {args.topic}")
    print(f"Target:      12th-grade graduate from India (non-English medium)")
    print(f"Max Retries: {args.max_retries}")
    if args.inject_fault:
        print(f"Fault Hook:  {args.inject_fault} (Attempt 0)")
    print("=======================================================\n")

    if args.demo_evolution:
        print("\n>>> DEMO EVOLUTION MODE ACTIVATED (Amendment 9) <<<")
        print("Running 3 sequential iterations to demonstrate rule synthesis, persistence, and prompt injection.\n")

        from src.memory.store import MemoryStore
        store = MemoryStore()

        for iteration in range(1, 4):
            print(f"\n=======================================================")
            print(f"            EVOLUTION RUN {iteration} OF 3")
            print(f"=======================================================")

            # Check rules before run
            active_rules_before = store.get_top_active_rules(limit=5)
            print(f"[Run {iteration}] Active Rules Loaded from Memory ({len(active_rules_before)}):")
            for r in active_rules_before:
                print(f"  * {r}")
            if not active_rules_before:
                print("  (None yet - cold start)")

            state = LessonState(
                topic=args.topic,
                max_retries=1,  # Keep attempts fast for demo
                fault_to_inject="hallucination" if iteration == 1 else None,
            )

            final_state_dict = graph.invoke(state)
            final_state = LessonState(**final_state_dict) if isinstance(final_state_dict, dict) else final_state_dict
            save_run_outputs(final_state)

            # Check rules after run
            active_rules_after = store.get_top_active_rules(limit=5)
            print(f"\n[Run {iteration} Finished] Memory Updated:")
            print(f"  Total Attempts: {len(final_state.attempts)}")
            print(f"  Active Rules in Memory Now ({len(active_rules_after)}):")
            for r in active_rules_after:
                print(f"  + {r}")

        print("\n=======================================================")
        print("        DEMO EVOLUTION COMPLETED SUCCESSFULLY")
        print(f"Active Rules Capped at 5 (Deduplicated)")
        print(f"Proposed Rubric: {settings.rubric_v2_proposed_path}")
        print("=======================================================\n")
        return

    graph = build_lesson_graph()

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

        # Print plain terminal summary (Rich UI comes in M7)
        print("\n----------------- EXECUTION SUMMARY -----------------")
        print(f"Run ID:         {final_state.run_id}")
        print(f"Total Attempts: {len(final_state.attempts)}")

        for a in final_state.attempts:
            status_str = (
                "PASSED (10/10)"
                if (a.evaluation and a.evaluation.passed)
                else "FAILED"
            )
            failing = (
                f" (Failing: {', '.join(a.evaluation.failing_checks)})"
                if (a.evaluation and a.evaluation.failing_checks)
                else ""
            )
            print(f"  Attempt {a.attempt_number}: {status_str}{failing}")
            if a.changes_made:
                print(f"    Changes: {a.changes_made[:120]}...")

        print("-----------------------------------------------------")
        final_status = (
            "PASSED & READY TO SHIP"
            if final_state.status == "passed"
            else "NEEDS HUMAN REVIEW (Best Attempt Selected)"
        )
        print(f"FINAL VERDICT:  {final_status}")
        print(f"Lesson File:    {lesson_file}")
        print(f"Rejection Log:  {settings.output_dir / 'rejection_log.json'}")
        print(f"Markdown Audit: {settings.output_dir / 'rejection_log.md'}")
        print("-----------------------------------------------------\n")

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

