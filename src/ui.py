"""Rich CLI Formatter and Visualizer for Lesson Agent (Milestone 7).

Provides terminal UI with:
- Per-attempt 10-check evaluation table grid
- Rejection critique details with verbatim evidence quotes
- Surgical revision summaries
- Final status cards
- Replay mode to render historical runs without API calls
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import settings

console = Console()

CHECK_METADATA = {
    "accuracy": {
        "type": "LLM Judge",
        "description": "Factual alignment with Lewis et al. (frozen weights, no retraining)",
    },
    "what_why_how": {
        "type": "LLM Judge",
        "description": "Explains What RAG is, Why models need it, and How it operates",
    },
    "key_points": {
        "type": "LLM Judge",
        "description": "Covers all 8 key concepts (retrieval, embeddings, vector db, etc.)",
    },
    "jargon_defined": {
        "type": "Deterministic + LLM",
        "description": "12 core terms defined at first use with zero technical prerequisite",
    },
    "reading_level": {
        "type": "Deterministic Code",
        "description": "Flesch-Kincaid Grade <= 7.0 and average sentence length <= 15.0 words",
    },
    "no_idioms": {
        "type": "LLM Judge",
        "description": "Zero Western idioms, colloquialisms, or culturally opaque phrases",
    },
    "worked_example": {
        "type": "LLM Judge",
        "description": "Concrete 3-step walkthrough set in an Indian college admission context",
    },
    "analogy": {
        "type": "LLM Judge",
        "description": "Intuitive open-book vs closed-book exam comparison",
    },
    "coherent_flow": {
        "type": "LLM Judge",
        "description": "Logical pedagogical progression from problem to solution to limits",
    },
    "wrap_up": {
        "type": "Deterministic + LLM",
        "description": "Worked Example, Summary, and Self-Check with 3 numbered questions",
    },
}


def render_banner(
    topic: str,
    max_retries: int,
    fault_hook: Optional[str] = None,
    generator_model: Optional[str] = None,
    judge_model: Optional[str] = None,
):
    """Render startup execution banner."""
    content = Text()
    content.append("AUTONOMOUS PEDAGOGICAL CONTENT SYSTEM\n", style="bold cyan")
    content.append(f"Topic:       {topic}\n", style="bold white")
    content.append(
        "Target:      12th-grade graduate from India (non-English medium background)\n",
        style="dim white",
    )
    content.append(f"Generator:   {generator_model or settings.generator_model} (temp=0.7)\n", style="green")
    content.append(f"LLM Judge:   {judge_model or settings.judge_model} (temp=0.2, independent)\n", style="magenta")
    content.append(f"Max Retries: {max_retries}\n", style="white")
    if fault_hook:
        content.append(f"Fault Hook:  {fault_hook} (Injected on Attempt 0)\n", style="bold red")

    console.print(Panel(content, title="[bold yellow]Agentic Workflow Initialized[/bold yellow]", border_style="cyan"))


def render_attempt_grid(
    attempt_num: int,
    total_attempts: int,
    checks: List[Dict[str, Any]],
    failing_checks: List[str],
    changes_made: Optional[str] = None,
):
    """Render visual table grid for an evaluation attempt."""
    passed_all = len(failing_checks) == 0

    title_color = "bold green" if passed_all else "bold red"
    grid_title = f"Attempt {attempt_num} Evaluation Matrix [{len(checks) - len(failing_checks)}/10 Passed]"

    table = Table(
        title=f"[{title_color}]{grid_title}[/{title_color}]",
        title_justify="left",
        border_style="dim",
        header_style="bold cyan",
    )
    table.add_column("#", justify="center", style="dim", width=4)
    table.add_column("Check ID", style="bold white", width=18)
    table.add_column("Type", style="magenta", width=22)
    table.add_column("Requirement / Standard", style="white", min_width=38)
    table.add_column("Status", justify="center", width=12)

    for idx, c in enumerate(checks, 1):
        cid = c.get("check_id", "")
        passed = c.get("passed", False)
        meta = CHECK_METADATA.get(cid, {"type": "Unknown", "description": ""})

        status_str = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        table.add_row(
            str(idx),
            cid,
            meta["type"],
            meta["description"],
            status_str,
        )

    console.print(table)

    # Rejection critique panel if any failures
    if not passed_all:
        critique_text = Text()
        for c in checks:
            if not c.get("passed", False):
                cid = c.get("check_id", "")
                reason = c.get("reason", "Standard violation detected")
                quote = c.get("evidence_quote", "")

                critique_text.append(f"\n✖ [{cid}]\n", style="bold red")
                critique_text.append(f"  Reason: {reason}\n", style="white")
                if quote:
                    critique_text.append(f"  Evidence Quote: \"{quote}\"\n", style="italic yellow")

        console.print(
            Panel(
                critique_text,
                title=f"[bold red]Rejection Critique & Diagnostic Evidence (Attempt {attempt_num})[/bold red]",
                border_style="red",
            )
        )

    # Surgical changes panel if present
    if changes_made:
        console.print(
            Panel(
                f"[cyan]{changes_made}[/cyan]",
                title=f"[bold cyan]Surgical Changes Applied on Attempt {attempt_num}[/bold cyan]",
                border_style="cyan",
            )
        )


def render_final_card(
    run_id: str,
    status: str,
    attempts_count: int,
    best_attempt_num: int,
    failing_count: int,
    lesson_path: Path,
):
    """Render shipping certification status card and artifact links."""
    is_shipped = status.lower() == "passed"

    card_text = Text()
    if is_shipped:
        card_text.append("STATUS: PASSED & READY TO SHIP\n\n", style="bold green")
        card_text.append(
            f"The lesson met all 10 hard pass/fail rubric checkpoints at Attempt {best_attempt_num}.\n",
            style="white",
        )
        card_text.append(
            "Pedagogical accessibility certified for 12th-grade Indian non-English-medium learners.\n\n",
            style="dim green",
        )
        border_style = "green"
        title = "[bold green]Quality Certification: APPROVED[/bold green]"
    else:
        card_text.append("STATUS: NEEDS HUMAN REVIEW (Best Attempt Selected)\n\n", style="bold yellow")
        card_text.append(
            f"Retry budget exhausted ({attempts_count} attempts made). Selecting best attempt (#{best_attempt_num}) "
            f"with fewest failing checks ({failing_count} failures remaining).\n\n",
            style="white",
        )
        border_style = "yellow"
        title = "[bold yellow]Quality Certification: ESCALATED TO HUMAN REVIEW[/bold yellow]"

    card_text.append(f"Run Identifier:     {run_id}\n", style="cyan")
    card_text.append(f"Published Lesson:   {lesson_path}\n", style="white")
    card_text.append(f"Rejection Log JSON: {settings.output_dir / 'rejection_log.json'}\n", style="white")
    card_text.append(f"Markdown Audit:     {settings.output_dir / 'rejection_log.md'}\n", style="white")
    card_text.append(f"SQLite Telemetry:   {settings.database_path}\n", style="dim")

    console.print(Panel(card_text, title=title, border_style=border_style))


def replay_saved_run(run_id_or_path: str):
    """Re-render the Rich CLI presentation for a saved run without making any API calls."""
    runs_dir = settings.output_dir / "runs"

    target_dir: Optional[Path] = None

    if run_id_or_path.lower() in ["latest", "last"]:
        all_runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda p: p.name)
        if not all_runs:
            console.print("[bold red]No saved runs found in outputs/runs/[/bold red]")
            return
        target_dir = all_runs[-1]
    else:
        direct_path = Path(run_id_or_path)
        if direct_path.is_dir():
            target_dir = direct_path
        elif (runs_dir / run_id_or_path).is_dir():
            target_dir = runs_dir / run_id_or_path

    if not target_dir or not target_dir.exists():
        console.print(f"[bold red]Run directory '{run_id_or_path}' not found.[/bold red]")
        return

    run_id = target_dir.name
    attempt_files = sorted(
        list(target_dir.glob("attempt_*.json")),
        key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0,
    )

    if not attempt_files:
        console.print(f"[bold red]No attempt traces found in {target_dir}[/bold red]")
        return

    console.print(f"\n[bold cyan]>>> REPLAYING SAVED RUN: {run_id} (Zero API Calls) <<<[/bold cyan]\n")
    render_banner(
        topic="Introduction to RAG (Retrieval-Augmented Generation)",
        max_retries=len(attempt_files) - 1,
        generator_model="Saved Trace",
        judge_model="Saved Trace",
    )

    best_attempt_num = 0
    fewest_fails = 999
    final_passed = False

    for att_file in attempt_files:
        data = json.loads(att_file.read_text(encoding="utf-8"))
        att_num = data.get("attempt_number", 0)
        passed = data.get("passed", False)
        failing = data.get("failing_checks", [])
        checks = data.get("checks", [])
        changes = data.get("changes_made")

        if len(failing) < fewest_fails:
            fewest_fails = len(failing)
            best_attempt_num = att_num

        if passed:
            final_passed = True

        render_attempt_grid(
            attempt_num=att_num,
            total_attempts=len(attempt_files),
            checks=checks,
            failing_checks=failing,
            changes_made=changes,
        )

    final_status = "passed" if final_passed else "needs_human_review"
    render_final_card(
        run_id=run_id,
        status=final_status,
        attempts_count=len(attempt_files),
        best_attempt_num=best_attempt_num,
        failing_count=fewest_fails,
        lesson_path=settings.output_dir / "lesson.md",
    )
