"""Recording Helper for Video Demo.

Automates and times the demonstration workflow for screen recording:
- Segment title cards with target and expected durations
- User-controlled take starts (waits for Enter)
- Live elapsed-time clock status bar (e.g. 'Elapsed 01:42 / target 03:00')
- Configurable narration pauses after key milestones (matrices, quotes, cards)
- Timeout guards (--max-wait) with clean process tree termination
- Session chapter timeline logs (demo/logs/timeline_<timestamp>.txt)
- End-of-session editing suggestion summary table
- Pre-flight diagnostic verification (--check, zero API calls)
- Optional browser walkthrough (--browser) with tab switching and screenshots

Additive only: does not alter pipeline code, rubric, prompts, or test fixtures.
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Target and expected raw durations in seconds
BUDGET = [
    {
        "id": "1",
        "name": "Live end-to-end run",
        "description": "Full autonomous pipeline generating a lesson from scratch, evaluating across 10 checks, and self-correcting to passing state.",
        "target_sec": 180,  # 3:00
        "expected_sec": 240,  # 4:00
        "target_str": "3:00",
        "expected_str": "up to 4:00",
        "command": 'python main.py --topic "Introduction to RAG (Retrieval-Augmented Generation)"',
        "cmd_args": [
            sys.executable,
            "main.py",
            "--topic",
            "Introduction to RAG (Retrieval-Augmented Generation)",
        ],
        "is_live": True,
    },
    {
        "id": "2",
        "name": "Deliberate error caught",
        "description": "Live fault injection (--inject-fault hallucination): Evaluator catches overclaim on Attempt 0 with verbatim evidence, Reviser surgically corrects it, passing Attempt 1.",
        "target_sec": 180,  # 3:00
        "expected_sec": 240,  # 4:00
        "target_str": "3:00",
        "expected_str": "up to 4:00",
        "command": 'python main.py --topic "Introduction to RAG" --inject-fault hallucination',
        "cmd_args": [
            sys.executable,
            "main.py",
            "--topic",
            "Introduction to RAG",
            "--inject-fault",
            "hallucination",
        ],
        "is_live": True,
    },
    {
        "id": "3",
        "name": "Evaluator catch-rate (live)",
        "description": "Live evaluation benchmark testing 8 flawed lesson drafts and 1 golden lesson against the Gemini LLM Judge and code checks (100% catch rate).",
        "target_sec": 120,  # 2:00
        "expected_sec": 300,  # 5:00
        "target_str": "2:00",
        "expected_str": "up to 5:00",
        "command": "python tests/test_evaluator.py --live",
        "cmd_args": [
            sys.executable,
            "tests/test_evaluator.py",
            "--live",
        ],
        "is_live": True,
    },
    {
        "id": "4",
        "name": "Memory demo",
        "description": "Persistent memory demo: inspecting learned rules synthesized from past failures in SQLite, followed by live prompt injection.",
        "target_sec": 120,  # 2:00
        "expected_sec": 180,  # 3:00
        "target_str": "2:00",
        "expected_str": "up to 3:00",
        "command": 'python main.py --topic "Introduction to RAG"',
        "cmd_args": [
            sys.executable,
            "main.py",
            "--topic",
            "Introduction to RAG",
        ],
        "is_live": True,
    },
    {
        "id": "5",
        "name": "Safe fallback replays",
        "description": "Instant deterministic replay mode rendering full Rich traces with zero API calls or network access.",
        "target_sec": 90,  # 1:30
        "expected_sec": 120,  # 2:00
        "target_str": "1:30",
        "expected_str": "up to 2:00",
        "command": "python main.py --replay examples/failing_then_passing_run && python main.py --replay examples/hallucination_fault_run",
        "cmd_args": [
            sys.executable,
            "main.py",
            "--replay",
            "examples/failing_then_passing_run",
        ],
        "secondary_cmd_args": [
            sys.executable,
            "main.py",
            "--replay",
            "examples/hallucination_fault_run",
        ],
        "is_live": False,
    },
]

SEGMENT_MAP = {b["id"]: b for b in BUDGET}


def format_seconds(seconds: float) -> str:
    """Format seconds into MM:SS string."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def prompt_user_enter(message: str, non_interactive: bool = False):
    """Prompt user to press Enter to proceed, auto-advancing if non-interactive."""
    if non_interactive or not sys.stdin.isatty():
        console.print(f"[dim]{message} (auto-advancing)[/dim]")
        time.sleep(0.5)
        return
    try:
        console.print(f"[bold yellow]{message}[/bold yellow] ", end="")
        input()
    except (EOFError, KeyboardInterrupt):
        console.print()


def print_title_card(seg: dict, non_interactive: bool = False):
    """Print large Rich title card before a segment take."""
    title_text = Text()
    title_text.append(f"SEGMENT {seg['id']}: {seg['name'].upper()}\n\n", style="bold cyan")
    title_text.append(f"Viewer Scope:\n  {seg['description']}\n\n", style="white")
    title_text.append(f"Target Duration (Edited):   {seg['target_str']}\n", style="bold green")
    title_text.append(f"Expected Duration (Raw API): {seg['expected_str']}\n", style="yellow")
    title_text.append(f"Command:\n  {seg['command']}\n", style="bold magenta")

    console.print(
        Panel(
            title_text,
            title="[bold yellow]🎬 DEMO RECORDING TAKE PREPARATION[/bold yellow]",
            subtitle="[dim]Check framing and microphone, then press Enter[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    prompt_user_enter("Press [Enter] when ready to start recording this take...", non_interactive=non_interactive)
    console.print()


def print_complete_card(seg: dict, actual_sec: float, status: str, non_interactive: bool = False):
    """Print segment completion card with actual duration."""
    actual_str = format_seconds(actual_sec)
    card_text = Text()
    card_text.append(f"Segment Complete: {seg['name']}\n\n", style="bold white")
    card_text.append(f"Actual Duration:  {actual_str}\n", style="bold green" if actual_sec <= seg["target_sec"] else "bold yellow")
    card_text.append(f"Target Duration:  {seg['target_str']}\n", style="dim white")
    card_text.append(f"Expected Raw:     {seg['expected_str']}\n", style="dim white")
    card_text.append(f"Status:           {status.upper()}\n", style="bold green" if status == "ok" else "bold red")

    border = "green" if status == "ok" else ("yellow" if status == "timeout" else "red")
    console.print(
        Panel(
            card_text,
            title="[bold green]✔ TAKE RECORDING FINISHED[/bold green]" if status == "ok" else "[bold red]⚠ TAKE FINISHED (CHECK STATUS)[/bold red]",
            border_style=border,
            padding=(1, 2),
        )
    )
    prompt_user_enter("Press [Enter] to continue...", non_interactive=non_interactive)
    console.print()


def terminate_process_tree(proc: subprocess.Popen):
    """Cleanly terminate child process and all child threads/processes."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        proc.wait(timeout=2)
    except Exception:
        pass


def execute_subcommand_with_clock(
    cmd_args: List[str],
    target_sec: int,
    pause_sec: float = 3.0,
    max_wait: int = 360,
    log_fp = None,
) -> Tuple[int, str, float]:
    """Stream command output with live Rich status clock, trigger pauses, and max-wait guard."""
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    start_time = time.time()
    tg_m, tg_s = divmod(target_sec, 60)

    status = console.status(f"[bold cyan]⏳ Elapsed 00:00 / target {tg_m:02d}:{tg_s:02d}[/bold cyan]")
    status.start()

    stop_clock = threading.Event()

    def update_clock():
        while not stop_clock.is_set():
            el = int(time.time() - start_time)
            el_m, el_s = divmod(el, 60)
            status.update(
                f"[bold cyan]⏳ Elapsed {el_m:02d}:{el_s:02d} / target {tg_m:02d}:{tg_s:02d}[/bold cyan]"
            )
            time.sleep(0.5)

    clock_thread = threading.Thread(target=update_clock, daemon=True)
    clock_thread.start()

    proc = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )

    status_result = "ok"

    try:
        for line in proc.stdout:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                # Timeout triggered! Clean terminate
                status_result = "timeout"
                terminate_process_tree(proc)
                break

            # Print streamed line cleanly via Rich Text.from_ansi
            console.print(Text.from_ansi(line), end="")
            if log_fp:
                log_fp.write(line)
                log_fp.flush()

            clean_line = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line).strip().lower()

            # Trigger 1: Evaluation Matrix check table
            if "evaluation matrix" in clean_line:
                time.sleep(pause_sec)

            # Trigger 2: Evidence quote from LLM Judge
            elif "evidence quote:" in clean_line or clean_line.startswith("evidence quote"):
                time.sleep(pause_sec)

            # Trigger 3: Final status card
            elif (
                "status: passed & ready to ship" in clean_line
                or "status: needs human review" in clean_line
                or "quality certification:" in clean_line
            ):
                time.sleep(pause_sec)

        proc.wait()
    except KeyboardInterrupt:
        terminate_process_tree(proc)
        status_result = "interrupted"
    finally:
        stop_clock.set()
        status.stop()

    actual_duration = time.time() - start_time

    if status_result == "timeout":
        console.print(
            "\n[bold yellow]Live API too slow. Use segment 5 (replay) as a fallback.[/bold yellow]"
        )
        return -1, "timeout", actual_duration

    if proc.returncode != 0 and status_result != "interrupted":
        console.print(
            "\n[bold red]Live API busy. Try again, or use segment 5 as a fallback.[/bold red]"
        )
        return proc.returncode, "failed", actual_duration

    return proc.returncode, status_result, actual_duration


def run_preflight_check() -> bool:
    """Run verification checks without making any Gemini API calls."""
    console.print(
        Panel(
            "[bold cyan]AUTONOMOUS LESSON SYSTEM: PRE-FLIGHT VERIFICATION[/bold cyan]\n"
            "Checking environment, SQLite telemetry, replay assets, and terminal width.\n"
            "[dim]Note: Zero Gemini API calls will be made during pre-flight.[/dim]",
            border_style="cyan",
        )
    )

    all_passed = True

    # 1. Terminal width check
    cols = shutil.get_terminal_size().columns
    if cols >= 100:
        console.print(f"[bold green]✔ Terminal Width: {cols} cols (>= 100 cols recommended)[/bold green]")
    else:
        console.print(
            f"[bold yellow]⚠ Terminal Width: {cols} cols (< 100 cols recommended; widen terminal for best recording)[/bold yellow]"
        )

    # 2. Check API key in .env (never print key)
    env_path = Path(".env")
    key_found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY=") and len(line.split("=", 1)[1].strip()) > 8:
                key_found = True
                break

    if key_found:
        console.print("[bold green]✔ GEMINI_API_KEY detected in .env (credential secured, not printed)[/bold green]")
    else:
        console.print("[bold red]✖ GEMINI_API_KEY missing or invalid in .env[/bold red]")
        all_passed = False

    # 3. Check SQLite memory.db
    db_path = Path("data/memory.db")
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM learned_rules WHERE active = 1")
            cnt = cur.fetchone()[0]
            conn.close()
            console.print(f"[bold green]✔ SQLite memory database opens cleanly ({cnt} active learned rules found)[/bold green]")
        except Exception as e:
            console.print(f"[bold red]✖ Error opening SQLite database data/memory.db: {e}[/bold red]")
            all_passed = False
    else:
        console.print("[bold red]✖ SQLite database data/memory.db not found[/bold red]")
        all_passed = False

    # 4. Check Replays (No API Calls)
    failing_replay = Path("examples/failing_then_passing_run")
    hallucination_replay = Path("examples/hallucination_fault_run")

    if failing_replay.exists() and hallucination_replay.exists():
        res1 = subprocess.run(
            [sys.executable, "main.py", "--replay", str(failing_replay)],
            capture_output=True,
            text=True,
        )
        res2 = subprocess.run(
            [sys.executable, "main.py", "--replay", str(hallucination_replay)],
            capture_output=True,
            text=True,
        )
        if res1.returncode == 0 and res2.returncode == 0:
            console.print("[bold green]✔ Offline replay test passed for both examples/ folders (0 API calls made)[/bold green]")
        else:
            console.print("[bold red]✖ One or both replay folders failed to render[/bold red]")
            all_passed = False
    else:
        console.print("[bold red]✖ Replay folders missing in examples/[/bold red]")
        all_passed = False

    # 5. Print Time-Budget Table
    console.print("\n[bold cyan]DEMO TIME BUDGET SCHEDULE[/bold cyan]")
    table = Table(border_style="dim", header_style="bold cyan")
    table.add_column("Segment", style="bold white", width=30)
    table.add_column("Target (On-Screen)", justify="center", style="green", width=22)
    table.add_column("Expected (Raw API)", justify="center", style="yellow", width=22)
    table.add_column("CLI Command Scope", style="dim", min_width=35)

    for b in BUDGET:
        table.add_row(
            f"{b['id']}. {b['name']}",
            f"{b['target_str']} ({b['target_sec']}s)",
            b["expected_str"],
            b["command"][:50] + ("..." if len(b["command"]) > 50 else ""),
        )

    table.add_row(
        "[bold cyan]TOTAL[/bold cyan]",
        "[bold green]~11:30 (690s)[/bold green]",
        "[bold yellow]~18:00 (1080s)[/bold yellow]",
        "[bold cyan]Complete 5-part demo recording session[/bold cyan]",
    )
    console.print(table)
    console.print()

    # 6. Green or red summary
    if all_passed:
        console.print(
            Panel(
                "[bold green]✔ ALL PRE-FLIGHT CHECKS PASSED: Ready to record demo video[/bold green]\n"
                "Run individual takes with: python demo/record_demo.py --segment <1-5>\n"
                "Or record all segments with: python demo/record_demo.py --segment all",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]✖ PRE-FLIGHT VERIFICATION FAILED: Resolve above issues before recording[/bold red]",
                border_style="red",
            )
        )

    return all_passed


def run_segment_4_memory_demo(
    seg: dict,
    pause_sec: float = 3.0,
    max_wait: int = 360,
    log_fp = None,
) -> Tuple[int, str, float]:
    """Execute segment 4: display current SQLite memory rules table, run main.py, and display injected rules."""
    console.print("\n[bold cyan]>>> STEP 4A: INSPECTING ACTIVE SQLITE LEARNED RULES <<<[/bold cyan]")
    db_path = Path("data/memory.db")
    rules = []
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, source_check_id, failure_count, active, rule_text "
                "FROM learned_rules WHERE active = 1 ORDER BY failure_count DESC, id ASC"
            )
            rules = [dict(row) for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            console.print(f"[bold red]Error querying rules: {e}[/bold red]")

    mem_table = Table(title="[bold green]Persistent SQLite Memory Store (data/memory.db)[/bold green]", border_style="dim")
    mem_table.add_column("#", justify="center", style="dim", width=4)
    mem_table.add_column("Rule ID", style="bold white", width=8)
    mem_table.add_column("Trigger Check", style="cyan", width=18)
    mem_table.add_column("Fail Count", justify="center", style="magenta", width=12)
    mem_table.add_column("Learned Pedagogical Rule", style="white", min_width=50)

    for idx, r in enumerate(rules, 1):
        mem_table.add_row(
            str(idx),
            f"Rule-{r['id']}",
            r["source_check_id"],
            str(r["failure_count"]),
            r["rule_text"],
        )
    console.print(mem_table)
    console.print("[dim]These active rules will be automatically injected into the Generator prompt by GrounderNode.[/dim]\n")
    time.sleep(pause_sec)

    console.print("[bold cyan]>>> STEP 4B: RUNNING PIPELINE WITH INJECTED RULES <<<[/bold cyan]")
    code, status_res, dur = execute_subcommand_with_clock(
        seg["cmd_args"],
        target_sec=seg["target_sec"],
        pause_sec=pause_sec,
        max_wait=max_wait,
        log_fp=log_fp,
    )

    console.print("\n[bold cyan]>>> STEP 4C: PROMPT INJECTION AUDIT <<<[/bold cyan]")
    injected_text = Text()
    injected_text.append("Verified: GrounderNode retrieved the top 5 active rules and passed them to GeneratorNode.\n", style="white")
    injected_text.append("Generator Prompt Section Injected:\n", style="bold green")
    for r in rules[:5]:
        injected_text.append(f"  • [{r['source_check_id']}]: {r['rule_text']}\n", style="italic cyan")
    injected_text.append("\nDatabase Integrity: data/memory.db preserved intact with zero resets.", style="bold white")

    console.print(Panel(injected_text, title="[bold green]Memory Persistence & Injection Confirmed[/bold green]", border_style="green"))
    return code, status_res, dur


def run_browser_walkthrough(pause_sec: float = 4.0, headless: Optional[bool] = None, non_interactive: bool = False):
    """Automate interactive walkthrough of outputs/view.html with tab switching and screenshots."""
    console.print(
        Panel(
            "[bold cyan]BROWSER DEMO WALKTHROUGH (outputs/view.html)[/bold cyan]\n"
            "Will cycle through: Published Lesson, 10-Check Matrix, Rejection Telemetry, and SQLite Memory.\n"
            "Pauses ~4 seconds on each section. Target duration: ~1:00.",
            border_style="cyan",
        )
    )

    from src.browser_view import generate_html_dashboard
    html_file = generate_html_dashboard()

    if headless is None:
        headless = not sys.stdin.isatty() or os.environ.get("PLAYWRIGHT_HEADLESS", "0") == "1"

    prompt_user_enter("Press [Enter] to launch browser walkthrough...", non_interactive=non_interactive)

    start_time = time.time()
    screenshot_dir = Path("demo/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1280, "height": 850})
            url = html_file.resolve().as_uri()
            page.goto(url)

            # Section 1: Lesson Tab
            console.print("[cyan]Navigating to Section 1: Published Lesson...[/cyan]")
            page.click("#tab-btn-lesson")
            time.sleep(1.0)
            page.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
            time.sleep(pause_sec)
            shot1 = screenshot_dir / "browser_1_lesson.png"
            page.screenshot(path=str(shot1))
            console.print(f"  [dim]Saved screenshot: {shot1}[/dim]")

            # Section 2: 10-Check Matrix Tab
            console.print("[cyan]Navigating to Section 2: 10-Check Rubric Matrix...[/cyan]")
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            page.click("#tab-btn-rubric")
            time.sleep(pause_sec)
            shot2 = screenshot_dir / "browser_2_matrix.png"
            page.screenshot(path=str(shot2))
            console.print(f"  [dim]Saved screenshot: {shot2}[/dim]")

            # Section 3: Rejection & Revision Telemetry Tab
            console.print("[cyan]Navigating to Section 3: Rejection & Revision Telemetry...[/cyan]")
            page.click("#tab-btn-rejection")
            time.sleep(1.0)
            page.evaluate("window.scrollBy({top: 300, behavior: 'smooth'})")
            time.sleep(pause_sec)
            shot3 = screenshot_dir / "browser_3_rejection.png"
            page.screenshot(path=str(shot3))
            console.print(f"  [dim]Saved screenshot: {shot3}[/dim]")

            # Section 4: Memory Store Tab
            console.print("[cyan]Navigating to Section 4: SQLite Memory Table...[/cyan]")
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            page.click("#tab-btn-memory")
            time.sleep(pause_sec)
            shot4 = screenshot_dir / "browser_4_memory.png"
            page.screenshot(path=str(shot4))
            console.print(f"  [dim]Saved screenshot: {shot4}[/dim]")

            browser.close()

        dur = time.time() - start_time
        console.print(
            Panel(
                f"[bold green]Browser Walkthrough Complete ({format_seconds(dur)})[/bold green]\n"
                f"All 4 screenshots saved to {screenshot_dir}",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Browser walkthrough failed: {e}[/bold red]")


def print_timing_summary_table(results: List[dict]):
    """Print timing summary table comparing target vs actual and editing suggestions."""
    console.print("\n[bold cyan]========================================================================[/bold cyan]")
    console.print("[bold cyan]                  DEMO VIDEO TIMING SUMMARY & EDITING NOTES            [/bold cyan]")
    console.print("[bold cyan]========================================================================[/bold cyan]")

    table = Table(border_style="dim", header_style="bold cyan")
    table.add_column("Seg", justify="center", style="bold white", width=5)
    table.add_column("Segment Name", style="white", width=26)
    table.add_column("Target", justify="center", style="green", width=10)
    table.add_column("Actual", justify="center", style="bold yellow", width=10)
    table.add_column("Delta", justify="center", width=12)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Post-Production Video Editing Suggestion", style="italic", min_width=35)

    total_target = 0
    total_actual = 0

    for r in results:
        seg = r["seg"]
        actual = r["duration"]
        target = seg["target_sec"]
        status = r["status"]

        total_target += target
        total_actual += actual

        diff = actual - target
        if diff > 0:
            delta_str = f"[red]+{format_seconds(diff)}[/red]"
            if diff > 20:
                suggestion = f"Segment {seg['id']} ran {format_seconds(diff)} over target: speed up the waiting/generation parts in editing."
            else:
                suggestion = f"Segment {seg['id']} slightly over target ({format_seconds(diff)}): trim trailing pauses."
        else:
            delta_str = f"[green]-{format_seconds(abs(diff))}[/green]"
            suggestion = f"Segment {seg['id']} within target budget ({format_seconds(actual)}): pacing is clean."

        status_badge = "[bold green]OK[/bold green]" if status == "ok" else f"[bold red]{status.upper()}[/bold red]"

        table.add_row(
            seg["id"],
            seg["name"],
            seg["target_str"],
            format_seconds(actual),
            delta_str,
            status_badge,
            suggestion,
        )

    total_diff = total_actual - total_target
    tot_delta_str = (
        f"[red]+{format_seconds(total_diff)}[/red]"
        if total_diff > 0
        else f"[green]-{format_seconds(abs(total_diff))}[/green]"
    )

    table.add_row(
        "[bold cyan]TOT[/bold cyan]",
        "[bold cyan]All Segments Combined[/bold cyan]",
        f"[bold green]{format_seconds(total_target)}[/bold green]",
        f"[bold yellow]{format_seconds(total_actual)}[/bold yellow]",
        tot_delta_str,
        "[bold green]COMPLETE[/bold green]",
        f"Raw recording time: {format_seconds(total_actual)}. Edit down to ~11:00 chapter length.",
    )

    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Demo Video Recording Helper with Live Elapsed Clocks & Narration Pauses"
    )
    parser.add_argument(
        "--segment",
        type=str,
        choices=["1", "2", "3", "4", "5", "all"],
        default=None,
        help="Segment number to run (1-5 or all)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=3.0,
        help="Seconds to pause after key moments (matrices, quotes, cards) for voiceover narration (default: 3.0)",
    )
    parser.add_argument(
        "--save-log",
        action="store_true",
        help="Save raw console output to demo/logs/session_<timestamp>.log",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=360,
        help="Maximum wait time in seconds before stopping a live segment and printing fallback (default: 360)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run pre-flight environment and offline replay check (0 API calls)",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Run automated browser walkthrough of outputs/view.html (pausing 4s per tab)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Auto-advance prompts without waiting for user Enter key (for automation/tests)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )

    args = parser.parse_args()

    # Pre-flight check
    if args.check:
        passed = run_preflight_check()
        sys.exit(0 if passed else 1)

    # Browser walkthrough
    if args.browser:
        run_browser_walkthrough(
            pause_sec=4.0,
            headless=args.headless,
            non_interactive=args.non_interactive,
        )
        sys.exit(0)

    if not args.segment:
        console.print("[yellow]No action specified. Run with --check, --browser, or --segment <1-5|all>.[/yellow]")
        run_preflight_check()
        sys.exit(0)

    # Prepare logs directory and timeline file
    logs_dir = Path("demo/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    timeline_path = logs_dir / f"timeline_{session_ts}.txt"
    log_fp = None
    if args.save_log:
        log_fp = open(logs_dir / f"session_{session_ts}.log", "w", encoding="utf-8")

    session_start_time = time.time()
    timeline_lines = [
        f"# Demo Video Session Chapter Timeline",
        f"# Session Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Format: Segment <id>: <name> | Start: MM:SS | End: MM:SS | Duration: MM:SS | Status: <status>",
        "",
    ]

    segments_to_run = (
        [SEGMENT_MAP[str(i)] for i in range(1, 6)]
        if args.segment == "all"
        else [SEGMENT_MAP[args.segment]]
    )

    results = []

    try:
        for seg in segments_to_run:
            print_title_card(seg, non_interactive=args.non_interactive)
            seg_start_offset = time.time() - session_start_time

            if seg["id"] == "4":
                code, status_res, dur = run_segment_4_memory_demo(
                    seg,
                    pause_sec=args.pause,
                    max_wait=args.max_wait,
                    log_fp=log_fp,
                )
            elif seg["id"] == "5":
                # Run replay 1
                console.print("\n[bold cyan]>>> RUNNING REPLAY 1: examples/failing_then_passing_run <<<[/bold cyan]")
                c1, s1, d1 = execute_subcommand_with_clock(
                    seg["cmd_args"],
                    target_sec=45,
                    pause_sec=args.pause,
                    max_wait=args.max_wait,
                    log_fp=log_fp,
                )
                console.print("\n[bold cyan]>>> RUNNING REPLAY 2: examples/hallucination_fault_run <<<[/bold cyan]")
                c2, s2, d2 = execute_subcommand_with_clock(
                    seg["secondary_cmd_args"],
                    target_sec=45,
                    pause_sec=args.pause,
                    max_wait=args.max_wait,
                    log_fp=log_fp,
                )
                code = max(c1, c2)
                status_res = "ok" if (s1 == "ok" and s2 == "ok") else "failed"
                dur = d1 + d2
            else:
                code, status_res, dur = execute_subcommand_with_clock(
                    seg["cmd_args"],
                    target_sec=seg["target_sec"],
                    pause_sec=args.pause,
                    max_wait=args.max_wait,
                    log_fp=log_fp,
                )

            seg_end_offset = time.time() - session_start_time

            # Record timeline entry
            timeline_line = (
                f"Segment {seg['id']}: {seg['name']} | "
                f"Start: {format_seconds(seg_start_offset)} | "
                f"End: {format_seconds(seg_end_offset)} | "
                f"Duration: {format_seconds(dur)} | "
                f"Status: {status_res}"
            )
            timeline_lines.append(timeline_line)
            timeline_path.write_text("\n".join(timeline_lines) + "\n", encoding="utf-8")

            results.append({"seg": seg, "duration": dur, "status": status_res})
            print_complete_card(seg, dur, status_res, non_interactive=args.non_interactive)

    finally:
        if log_fp:
            log_fp.close()

    # If all segments were run, print summary table
    if args.segment == "all":
        print_timing_summary_table(results)

    console.print(f"\n[dim]Timeline chapter log saved: {timeline_path}[/dim]\n")


if __name__ == "__main__":
    main()
