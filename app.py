"""Streamlit Prototype UI for Autonomous Lesson Generation and Evaluation.

A thin interactive visual layer on top of the LangGraph state machine.
Supports live cyclic generation/evaluation runs and zero-network saved run replays.
Reuses the exact graph entry point and schemas without altering pipeline logic.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from src.config import settings
from src.graph import build_lesson_graph, save_run_outputs
from src.schemas import LessonState
from src.ui import CHECK_METADATA

st.set_page_config(page_title="Autonomous Lesson Generator & Evaluator", page_icon="🎓", layout="wide")


def get_saved_run_dirs() -> List[Path]:
    """Discover run directories containing attempt traces in examples, submission, and outputs."""
    found: List[Path] = []
    for parent in [Path("examples"), Path("submission"), Path("outputs/runs")]:
        if parent.is_dir():
            for child in sorted(parent.iterdir()):
                if child.is_dir() and list(child.glob("attempt_*.json")):
                    found.append(child)
    return found


def parse_run_dir(folder: Path) -> Dict[str, Any]:
    """Parse saved attempt traces from disk into a uniform run_data dictionary."""
    files = sorted(list(folder.glob("attempt_*.json")), key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0)
    if not files:
        return {}
    attempts, fewest_fails, best_attempt, final_passed, run_id = [], 999, None, False, folder.name
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        failing = d.get("failing_checks", [])
        passed = d.get("passed", len(failing) == 0)
        run_id = d.get("run_id", run_id)
        att = {
            "attempt_number": d.get("attempt_number", 0), "passed": passed, "failing_checks": failing,
            "changes_made": d.get("changes_made"), "checks": d.get("checks", []), "content": d.get("content", ""),
        }
        attempts.append(att)
        if len(failing) < fewest_fails:
            fewest_fails, best_attempt = len(failing), att
        if passed:
            final_passed = True
    status = "passed" if final_passed else "needs_human_review"
    rej_records = [{
        "attempt_number": a["attempt_number"],
        "evaluation": {"passed": a["passed"], "failing_checks": a["failing_checks"], "failed_check_details": [
            {"check_id": c.get("check_id"), "reason": c.get("reason"), "evidence_quote": c.get("evidence_quote", "")}
            for c in a["checks"] if not c.get("passed", False)
        ]}, "changes_made": a["changes_made"],
    } for a in attempts]
    rej_json = json.dumps({"run_id": run_id, "status": status, "attempts_count": len(attempts), "rejection_log": rej_records}, indent=2)
    logs = ["✅ Grounder: Loaded domain facts, glossary, and memory rules", "✅ Planner: Synthesized curriculum outline and 8 concepts", "✅ Generator: Drafted Attempt 0"]
    for idx, a in enumerate(attempts):
        if idx > 0:
            logs.append(f"✅ Reviser: Applied surgical fixes for Attempt {a['attempt_number']}")
        logs.append(f"✅ Evaluator: Evaluated Attempt {a['attempt_number']} ({len(a['failing_checks'])} failing checks)")
        if not a["passed"] and idx < len(attempts) - 1:
            logs.append("🔀 Router: Threshold failed & retries remaining -> Dispatched to Reviser")
    logs.extend([f"🔀 Router: Dispatched to Reflector (Final Status: {status.upper()})", "✅ Reflector: Persisted telemetry to SQLite memory"])
    return {
        "run_id": run_id, "topic": "Introduction to RAG (Retrieval-Augmented Generation)", "status": status,
        "attempts": attempts, "best_attempt": best_attempt, "lesson_md": best_attempt["content"] if best_attempt else "",
        "rejection_log_json": rej_json, "logs": logs,
    }


def execute_live_run(topic: str, max_retries: int, fault: Optional[str], status_box) -> Dict[str, Any]:
    """Execute LangGraph live via stream(), updating real-time node progression."""
    graph = build_lesson_graph()
    initial_state = LessonState(topic=topic, max_retries=max_retries, fault_to_inject=fault if fault != "none" else None)
    logs, last_values = [], None
    for mode, payload in graph.stream(initial_state, stream_mode=["updates", "values"]):
        if mode == "updates":
            for node_name, upd in payload.items():
                msg = f"✅ {node_name.capitalize()}Node completed."
                if node_name == "evaluator":
                    curr_attempts = upd.get("attempts", [])
                    if curr_attempts:
                        att = curr_attempts[-1]
                        att_num = getattr(att, "attempt_number", 0)
                        passed = att.evaluation.passed if att.evaluation else False
                        msg = f"✅ EvaluatorNode: Attempt {att_num} evaluated (Passed: {passed})."
                        logs.append(msg)
                        status_box.write(msg)
                        router_msg = f"🔀 RouterNode: Dispatched to {'Reflector' if passed or att_num >= max_retries else 'Reviser'}."
                        logs.append(router_msg)
                        status_box.write(router_msg)
                        continue
                logs.append(msg)
                status_box.write(msg)
        elif mode == "values":
            last_values = payload
    if not last_values:
        raise ValueError("Pipeline did not return state values.")
    final_state = LessonState(**last_values) if isinstance(last_values, dict) else last_values
    save_run_outputs(final_state)
    attempts = [{
        "attempt_number": a.attempt_number, "passed": a.evaluation.passed if a.evaluation else False,
        "failing_checks": a.evaluation.failing_checks if a.evaluation else [], "changes_made": a.changes_made,
        "checks": [c.model_dump() for c in (a.evaluation.checks if a.evaluation else [])], "content": a.content,
    } for a in final_state.attempts]
    best = final_state.get_best_attempt()
    best_dict = attempts[best.attempt_number] if best and best.attempt_number < len(attempts) else (attempts[0] if attempts else {})
    lesson_path, rej_path = settings.output_dir / "lesson.md", settings.output_dir / "rejection_log.json"
    return {
        "run_id": final_state.run_id, "topic": final_state.topic, "status": final_state.status,
        "attempts": attempts, "best_attempt": best_dict,
        "lesson_md": lesson_path.read_text(encoding="utf-8") if lesson_path.exists() else best_dict.get("content", ""),
        "rejection_log_json": rej_path.read_text(encoding="utf-8") if rej_path.exists() else "{}", "logs": logs,
    }


# Session State Initialization
if "run_data" not in st.session_state:
    st.session_state["run_data"] = None
if "running" not in st.session_state:
    st.session_state["running"] = False

# Sidebar Configuration
st.sidebar.title("Configuration")
api_key_present = bool(settings.gemini_api_key)
mode_choice = st.sidebar.radio("Mode", ["Live run (uses Gemini API key)", "Replay saved run (no API key needed)"], index=0 if api_key_present else 1)
saved_runs = get_saved_run_dirs()
saved_options = [p.as_posix() for p in saved_runs]

if mode_choice.startswith("Live"):
    if not api_key_present:
        st.sidebar.error("⚠️ GEMINI_API_KEY is not set in .env. Switch to Replay mode or set key in .env.")
    topic = st.sidebar.text_input("Topic", value="Introduction to RAG (Retrieval-Augmented Generation)")
    fault_inject = st.sidebar.selectbox("Fault Injection (Attempt 0)", ["none", "hallucination", "jargon", "no_example", "long_sentences", "no_quiz"])
    max_retries = st.sidebar.number_input("Max Retries", min_value=1, max_value=2, value=2)
    run_btn = st.sidebar.button("Run pipeline", type="primary", disabled=not api_key_present or st.session_state["running"])
else:
    st.sidebar.caption("Offline trace replay: zero API keys and zero network calls.")
    selected_folder_str = st.sidebar.selectbox("Saved Run Folder", saved_options if saved_options else ["None found"])
    replay_btn = st.sidebar.button("Replay", type="primary", disabled=not saved_options)
    run_btn = False

if st.session_state["run_data"] is None and saved_runs:
    st.session_state["run_data"] = parse_run_dir(saved_runs[0])

if mode_choice.startswith("Replay") and replay_btn and selected_folder_str != "None found":
    st.session_state["run_data"] = parse_run_dir(Path(selected_folder_str))
    st.sidebar.success(f"Loaded: {Path(selected_folder_str).name}")

st.title("Autonomous Lesson Generator & Evaluator")
st.caption("Cyclic multi-node agent state machine powered by LangGraph, deterministic checks, and LLM judge.")
tabs = st.tabs(["Live progress", "Evaluation", "Rejection log", "Final lesson", "Memory", "Compare attempts"])

# Tab 1: Live progress
with tabs[0]:
    st.subheader("Workflow Execution & Node Progression")
    status_holder = st.empty()
    if mode_choice.startswith("Live") and run_btn and api_key_present and not st.session_state["running"]:
        st.session_state["running"] = True
        with status_holder.status("Running pipeline workflow...", expanded=True) as status_box:
            try:
                result = execute_live_run(topic, max_retries, fault_inject, status_box)
                st.session_state["run_data"] = result
                status_box.update(label=f"Pipeline Completed: {result['status'].upper()}", state="complete", expanded=False)
                st.success(f"Execution finished! Final status: **{result['status'].upper()}**")
            except Exception as e:
                err = str(e)
                status_box.update(label="Pipeline Failed", state="error", expanded=True)
                msg = "Rate limit exceeded (API 429). Retry shortly." if ("429" in err or "ResourceExhausted" in err) else ("Gemini API unavailable (503). Retry shortly." if ("503" in err or "Unavailable" in err) else f"Execution error: {err}")
                st.error(msg)
            finally:
                st.session_state["running"] = False

    data = st.session_state.get("run_data")
    if data:
        c1, c2, c3 = st.columns(3)
        c1.metric("Run Identifier", data["run_id"])
        c2.metric("Total Attempts", len(data["attempts"]))
        c3.metric("Status Badge", data["status"].upper())
        st.markdown("#### Completed Progression Steps")
        for log_entry in data.get("logs", []):
            st.write(log_entry)
    else:
        st.info("No active run data. Click 'Run pipeline' or 'Replay'.")

# Tab 2: Evaluation
with tabs[1]:
    st.subheader("10-Check Binary Evaluation Matrix")
    data = st.session_state.get("run_data")
    if data and data["attempts"]:
        for a in data["attempts"]:
            lbl = "PASSED (10/10)" if a["passed"] else f"FAILED ({len(a['failing_checks'])} failing checks)"
            st.markdown(f"### Attempt #{a['attempt_number']} &mdash; `{lbl}`")
            rows = [{
                "Check ID": c.get("check_id", ""), "Result": "PASS" if c.get("passed") else "FAIL",
                "Type": CHECK_METADATA.get(c.get("check_id", ""), {}).get("type", "Deterministic / LLM"),
                "Diagnostic Reason": c.get("reason", ""), "Evidence Quote": c.get("evidence_quote", ""),
            } for c in a["checks"]]
            df = pd.DataFrame(rows)
            st.dataframe(
                df.style.apply(lambda r: [
                    "background-color: #fee2e2; color: #991b1b; font-weight: bold;" if r["Result"] == "FAIL"
                    else "background-color: #f0fdf4; color: #166534;"
                ] * len(r), axis=1),
                use_container_width=True, hide_index=True,
            )
    else:
        st.info("No evaluation data available. Run or replay a pipeline execution.")

# Tab 3: Rejection log
with tabs[2]:
    st.subheader("Rejection Critique & Surgical Changes")
    data = st.session_state.get("run_data")
    if data and data["attempts"]:
        for a in data["attempts"]:
            with st.expander(f"Attempt #{a['attempt_number']} Rejection & Revision Details", expanded=not a["passed"]):
                if a["failing_checks"]:
                    st.error(f"Failing Checks: {', '.join(a['failing_checks'])}")
                    for c in a["checks"]:
                        if not c.get("passed"):
                            st.markdown(f"**{c.get('check_id')}**: {c.get('reason')}")
                            if c.get("evidence_quote"):
                                st.caption(f"Verbatim Evidence: *\"{c.get('evidence_quote')}\"*")
                else:
                    st.success("All 10 checks passed with zero rejection.")
                if a.get("changes_made"):
                    st.info(f"**Surgical Changes Made:**\n\n{a['changes_made']}")
    else:
        st.info("No rejection logs available.")

# Tab 4: Final lesson
with tabs[3]:
    st.subheader("Published Educational Artifact")
    data = st.session_state.get("run_data")
    if data and data.get("lesson_md"):
        if data["status"] == "passed":
            st.success("### STATUS: PASSED & READY TO SHIP\nAll 10 hard pass/fail checkpoints satisfied. Certified for publication.")
        else:
            st.warning("### STATUS: NEEDS HUMAN REVIEW\nRetry budget exhausted. Best attempt selected with fewest failing checks.")
        c1, c2 = st.columns(2)
        c1.download_button("📥 Download lesson.md", data["lesson_md"], file_name="lesson.md", mime="text/markdown", use_container_width=True)
        c2.download_button("📥 Download rejection_log.json", data["rejection_log_json"], file_name="rejection_log.json", mime="application/json", use_container_width=True)
        st.markdown("---")
        st.markdown(data["lesson_md"])
    else:
        st.info("No final lesson generated yet.")

# Tab 5: Memory
with tabs[4]:
    st.subheader("Persistent SQLite Learned Rules")
    db_path = Path(settings.database_path)
    if not db_path.exists():
        st.info("No learned rules yet (database does not exist).")
    else:
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_rules'")
                if not cur.fetchone():
                    st.info("No learned rules yet (table missing).")
                else:
                    cur.execute("SELECT id, source_check_id, failure_count, active, rule_text, created_at FROM learned_rules ORDER BY failure_count DESC, id ASC")
                    rows = cur.fetchall()
                    if not rows:
                        st.info("No learned rules yet (table empty).")
                    else:
                        st.dataframe(pd.DataFrame(rows, columns=["ID", "Source Check", "Count", "Active", "Rule Text", "Created At"]), use_container_width=True, hide_index=True)
        except Exception:
            st.info("No learned rules yet.")

# Tab 6: Compare attempts
with tabs[5]:
    st.subheader("Side-by-Side Attempt Comparison")
    data = st.session_state.get("run_data")
    if data and len(data["attempts"]) > 1:
        att_options = [f"Attempt #{a['attempt_number']}" for a in data["attempts"]]
        s1, s2 = st.columns(2)
        sel_a, sel_b = s1.selectbox("Base Attempt", att_options, index=0), s2.selectbox("Revised Attempt", att_options, index=1)
        att_a, att_b = data["attempts"][att_options.index(sel_a)], data["attempts"][att_options.index(sel_b)]
        c1, c2 = st.columns(2)
        c1.markdown(f"#### {sel_a} ({'PASSED' if att_a['passed'] else 'FAILED'})")
        c1.text_area(f"{sel_a} Text", att_a["content"], height=550, disabled=True, key="cmp_txt_a")
        c2.markdown(f"#### {sel_b} ({'PASSED' if att_b['passed'] else 'FAILED'})")
        c2.text_area(f"{sel_b} Text", att_b["content"], height=550, disabled=True, key="cmp_txt_b")
    elif data and len(data["attempts"]) == 1:
        st.info("Attempt 0 passed on the first try with 0 revisions. No second attempt to compare.")
    else:
        st.info("No attempts available to compare.")
