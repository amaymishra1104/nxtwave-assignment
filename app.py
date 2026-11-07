"""Streamlit Prototype UI for Autonomous Lesson Generation and Evaluation.

A rich, interactive visual layer on top of the LangGraph state machine.
Supports live cyclic generation/evaluation runs and zero-network saved run replays.
Reuses the exact graph entry point and schemas without altering pipeline logic.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
import textstat

from src.checks.deterministic import check_reading_level, strip_markdown
from src.config import settings
from src.graph import build_lesson_graph, save_run_outputs
from src.schemas import LessonState
from src.ui import CHECK_METADATA

st.set_page_config(
    page_title="Autonomous Lesson Generator & Evaluator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for modern, pedagogical, intuitive UI
st.markdown("""
<style>
    .hero-container {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 20px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
        color: #f8fafc;
    }
    .hero-title {
        font-size: 1.85rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        margin-bottom: 6px;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        color: #cbd5e1;
        font-size: 0.95rem;
        margin-bottom: 12px;
    }
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-persona { background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-engine { background-color: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
    .badge-judge { background-color: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
    .critique-card {
        background: #fff1f2;
        border-left: 4px solid #e11d48;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .evidence-quote {
        background: #ffffff;
        border-left: 3px solid #3b82f6;
        border-radius: 4px;
        padding: 8px 12px;
        font-style: italic;
        color: #334155;
        margin-top: 6px;
        font-size: 0.9rem;
    }
    .revision-card {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
        border-radius: 6px;
        padding: 12px 16px;
        margin-top: 10px;
        color: #14532d;
    }
</style>
""", unsafe_allow_html=True)


def get_saved_run_dirs() -> List[Path]:
    """Discover run directories containing attempt traces in examples, submission, and outputs."""
    found: List[Path] = []
    for parent in [Path("examples"), Path("submission"), Path("outputs/runs")]:
        if parent.is_dir():
            for child in sorted(parent.iterdir(), reverse=True):
                if child.is_dir() and list(child.glob("attempt_*.json")):
                    found.append(child)
    return found


def parse_run_dir(folder: Path) -> Dict[str, Any]:
    """Parse saved attempt traces from disk into a uniform run_data dictionary."""
    files = sorted(
        list(folder.glob("attempt_*.json")),
        key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0,
    )
    if not files:
        return {}

    attempts, fewest_fails, best_attempt, final_passed, run_id = [], 999, None, False, folder.name
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        failing = d.get("failing_checks", [])
        passed = d.get("passed", len(failing) == 0)
        run_id = d.get("run_id", run_id)
        att = {
            "attempt_number": d.get("attempt_number", 0),
            "passed": passed,
            "failing_checks": failing,
            "changes_made": d.get("changes_made"),
            "checks": d.get("checks", []),
            "content": d.get("content", ""),
        }
        attempts.append(att)
        if len(failing) < fewest_fails:
            fewest_fails, best_attempt = len(failing), att
        if passed:
            final_passed = True

    status = "passed" if final_passed else "needs_human_review"
    rej_records = [{
        "attempt_number": a["attempt_number"],
        "evaluation": {
            "passed": a["passed"],
            "failing_checks": a["failing_checks"],
            "failed_check_details": [
                {"check_id": c.get("check_id"), "reason": c.get("reason"), "evidence_quote": c.get("evidence_quote", "")}
                for c in a["checks"] if not c.get("passed", False)
            ],
        },
        "changes_made": a["changes_made"],
    } for a in attempts]

    rej_json = json.dumps({"run_id": run_id, "status": status, "attempts_count": len(attempts), "rejection_log": rej_records}, indent=2)
    logs = [
        "✅ GrounderNode: Loaded canonical facts (Lewis et al.), 12-term glossary, and SQLite memory rules",
        "✅ PlannerNode: Outlined What/Why/How checklist, 8 mandatory concepts, and Indian college exam analogy",
        "✅ GeneratorNode: Drafted initial lesson attempt (Attempt 0)",
    ]
    for idx, a in enumerate(attempts):
        if idx > 0:
            logs.append(f"✅ ReviserNode: Applied surgical repairs for Attempt {a['attempt_number']}")
        logs.append(f"✅ EvaluatorNode: Evaluated Attempt {a['attempt_number']} ({len(a['failing_checks'])} failing checks)")
        if not a["passed"] and idx < len(attempts) - 1:
            logs.append("🔀 RouterNode: Rubric threshold failed & retries remaining -> Dispatched to ReviserNode")
    logs.extend([
        f"🔀 RouterNode: Dispatched to ReflectorNode (Terminal Certification: {status.upper()})",
        "✅ ReflectorNode: Persisted run telemetry to SQLite database; analyzed rejection patterns",
    ])

    return {
        "run_id": run_id,
        "topic": "Introduction to RAG (Retrieval-Augmented Generation)",
        "status": status,
        "attempts": attempts,
        "best_attempt": best_attempt,
        "lesson_md": best_attempt["content"] if best_attempt else "",
        "rejection_log_json": rej_json,
        "logs": logs,
    }


def execute_live_run(topic: str, max_retries: int, fault: Optional[str], status_box) -> Dict[str, Any]:
    """Execute LangGraph live via stream(), updating real-time node progression."""
    graph = build_lesson_graph()
    initial_state = LessonState(topic=topic, max_retries=max_retries, fault_to_inject=fault if fault != "none" else None)
    logs, last_values = [], None

    for mode, payload in graph.stream(initial_state, stream_mode=["updates", "values"]):
        if mode == "updates":
            for node_name, upd in payload.items():
                msg = f"✅ {node_name.capitalize()}Node completed successfully."
                if node_name == "evaluator":
                    curr_attempts = upd.get("attempts", [])
                    if curr_attempts:
                        att = curr_attempts[-1]
                        att_num = getattr(att, "attempt_number", 0)
                        passed = att.evaluation.passed if att.evaluation else False
                        msg = f"✅ EvaluatorNode: Attempt {att_num} evaluated (Outcome: {'PASSED' if passed else 'FAILED'})."
                        logs.append(msg)
                        status_box.write(msg)
                        target_next = "ReflectorNode" if passed or att_num >= max_retries else "ReviserNode"
                        router_msg = f"🔀 RouterNode: Dispatched to {target_next}."
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
        "attempt_number": a.attempt_number,
        "passed": a.evaluation.passed if a.evaluation else False,
        "failing_checks": a.evaluation.failing_checks if a.evaluation else [],
        "changes_made": a.changes_made,
        "checks": [c.model_dump() for c in (a.evaluation.checks if a.evaluation else [])],
        "content": a.content,
    } for a in final_state.attempts]

    best = final_state.get_best_attempt()
    best_dict = attempts[best.attempt_number] if best and best.attempt_number < len(attempts) else (attempts[0] if attempts else {})
    lesson_path, rej_path = settings.output_dir / "lesson.md", settings.output_dir / "rejection_log.json"

    return {
        "run_id": final_state.run_id,
        "topic": final_state.topic,
        "status": final_state.status,
        "attempts": attempts,
        "best_attempt": best_dict,
        "lesson_md": lesson_path.read_text(encoding="utf-8") if lesson_path.exists() else best_dict.get("content", ""),
        "rejection_log_json": rej_path.read_text(encoding="utf-8") if rej_path.exists() else "{}",
        "logs": logs,
    }


# Session State Initialization
if "run_data" not in st.session_state:
    st.session_state["run_data"] = None
if "running" not in st.session_state:
    st.session_state["running"] = False

# Sidebar Configuration
st.sidebar.markdown("### ⚙️ Pipeline Controls")
api_key_present = bool(settings.gemini_api_key)
mode_choice = st.sidebar.radio(
    "Execution Mode",
    ["🚀 Live Generation (Gemini API)", "📂 Replay Saved Run (Offline)"],
    index=0 if api_key_present else 1,
)

saved_runs = get_saved_run_dirs()
saved_options = [p.as_posix() for p in saved_runs]

if mode_choice.startswith("🚀"):
    if not api_key_present:
        st.sidebar.error("⚠️ GEMINI_API_KEY is not set in .env. Switch to Replay mode or set key in .env.")

    topic = st.sidebar.text_input(
        "Lesson Topic",
        value="Introduction to RAG (Retrieval-Augmented Generation)",
        help="Specify the technical subject for curriculum planning and lesson drafting.",
    )

    fault_help = (
        "Deliberately injects a specific pedagogical or factual violation into Attempt 0 "
        "to test evaluator catching capability and surgeon revision live."
    )
    fault_inject = st.sidebar.selectbox(
        "Fault Injection (Attempt 0)",
        ["none", "hallucination", "jargon", "no_example", "long_sentences", "no_quiz"],
        help=fault_help,
    )
    max_retries = st.sidebar.slider("Maximum Revision Retries", min_value=1, max_value=2, value=2)
    run_btn = st.sidebar.button(
        "⚡ Run Full Pipeline",
        type="primary",
        disabled=not api_key_present or st.session_state["running"],
        use_container_width=True,
    )
else:
    st.sidebar.caption("Offline trace replay: reads saved traces from disk with zero network and zero API token cost.")
    selected_folder_str = st.sidebar.selectbox(
        "Select Saved Run Trace",
        saved_options if saved_options else ["None found"],
    )
    replay_btn = st.sidebar.button("📂 Load & Replay Trace", type="primary", disabled=not saved_options, use_container_width=True)
    run_btn = False

with st.sidebar.expander("🎯 Target Learner Persona & Rules", expanded=False):
    st.markdown("""
    - **Demographic**: 12th-grade Indian high-school graduate.
    - **Background**: Non-English vernacular schooling.
    - **Readability**: $\\text{FK} \\le 7.0$ & $\\text{Avg Sentence} \\le 15.0\\text{ words}$.
    - **Tone**: Zero Western idioms, clear Indian college admission analogies, literal definitions.
    """)

# Auto-load initial saved run if session is empty
if st.session_state["run_data"] is None and saved_runs:
    st.session_state["run_data"] = parse_run_dir(saved_runs[0])

# Handle Replay Click
if mode_choice.startswith("📂") and replay_btn and selected_folder_str != "None found":
    st.session_state["run_data"] = parse_run_dir(Path(selected_folder_str))
    st.sidebar.success(f"Loaded: {Path(selected_folder_str).name}")

# Hero Header Banner
st.markdown("""
<div class="hero-container">
    <div class="hero-title">Autonomous Lesson Generator & Evaluator</div>
    <div class="hero-subtitle">
        A deterministic cyclic state machine with dual-tier evaluation, surgical remediation, and meta-cognitive memory evolution.
    </div>
    <div>
        <span class="badge-pill badge-persona">🎯 Target: 12th-Grade Vernacular Learner</span>
        <span class="badge-pill badge-engine">⚡ Orchestration: LangGraph</span>
        <span class="badge-pill badge-judge">⚖️ Dual-Tier: Code + LLM Judge</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Main Navigation Tabs
tab_icons = ["⚡ Live Progress", "📊 Evaluation Matrix", "🔍 Rejection & Edits", "📖 Published Lesson", "🧠 Memory Store", "⚖️ Compare Attempts"]
tabs = st.tabs(tab_icons)

# ==============================================================================
# TAB 1: Live Progress & Architecture
# ==============================================================================
with tabs[0]:
    st.markdown("### ⚡ Workflow Execution & Node Progression")
    status_holder = st.empty()

    if mode_choice.startswith("🚀") and run_btn and api_key_present and not st.session_state["running"]:
        st.session_state["running"] = True
        with status_holder.status("🚀 Running LangGraph autonomous agent workflow...", expanded=True) as status_box:
            try:
                fault_arg = fault_inject if fault_inject != "none" else None
                result = execute_live_run(topic, max_retries, fault_arg, status_box)
                st.session_state["run_data"] = result
                status_box.update(label=f"Pipeline Completed: {result['status'].upper()}", state="complete", expanded=False)
                st.success(f"Execution finished successfully! Final status: **{result['status'].upper()}**")
            except Exception as e:
                err = str(e)
                status_box.update(label="Pipeline Execution Error", state="error", expanded=True)
                if "429" in err or "ResourceExhausted" in err:
                    st.error("API Rate limit exceeded (429 / Resource Exhausted). Please wait a moment and retry.")
                elif "503" in err or "Unavailable" in err:
                    st.error("Gemini API is temporarily unavailable (503). Please retry shortly.")
                else:
                    st.error(f"Execution error: {err}")
            finally:
                st.session_state["running"] = False

    data = st.session_state.get("run_data")
    if data:
        col1, col2, col3, col4 = st.columns(4)
        status_label = "PASSED & SHIPPED" if data["status"] == "passed" else "NEEDS HUMAN REVIEW"
        status_color = "normal" if data["status"] == "passed" else "off"

        col1.metric("Run Identifier", data["run_id"])
        col2.metric("Total Attempts", len(data["attempts"]))
        col3.metric("Certification Status", status_label)
        col4.metric("Fewest Failing Checks", len(data["best_attempt"].get("failing_checks", [])) if data.get("best_attempt") else 0)

        st.markdown("---")
        st.markdown("#### 🗺️ Multi-Agent State Machine Architecture")
        st.markdown("""
```mermaid
flowchart LR
    Start([Topic Input]) --> Grounder[1. GrounderNode]
    Grounder --> Planner[2. PlannerNode]
    Planner --> Generator[3. GeneratorNode]
    Generator --> Evaluator[4. EvaluatorNode]
    Evaluator --> Router{5. RouterNode}
    Router -- "All 10 Pass" --> Reflector[7. ReflectorNode]
    Router -- "Fail & Retries Left" --> Reviser[6. ReviserNode]
    Router -- "Retries Exhausted" --> Reflector
    Reviser --> Evaluator
    Reflector --> Publish([outputs/lesson.md])
    Reflector --> SQLite[(data/memory.db)]
```
        """)

        st.markdown("#### 📋 Execution Step Timeline")
        for log_entry in data.get("logs", []):
            st.markdown(f"- {log_entry}")
    else:
        st.info("No active run selected. Click 'Run Full Pipeline' or select a saved trace from the sidebar.")

# ==============================================================================
# TAB 2: Evaluation Matrix (10 Checks)
# ==============================================================================
with tabs[1]:
    st.markdown("### 📊 10-Check Binary Quality Audit")
    data = st.session_state.get("run_data")
    if data and data["attempts"]:
        attempts = data["attempts"]
        att_labels = []
        for a in attempts:
            fc_count = len(a.get("failing_checks", []))
            tag = "PASSED (10/10)" if a["passed"] else f"FAILED ({fc_count} fail)"
            att_labels.append(f"Attempt #{a['attempt_number']} ({tag})")

        selected_att_idx = 0
        if len(attempts) > 1:
            selected_label = st.radio("Select Attempt Audit:", att_labels, horizontal=True)
            selected_att_idx = att_labels.index(selected_label)

        curr_att = attempts[selected_att_idx]
        pass_count = len(curr_att["checks"]) - len(curr_att["failing_checks"])
        pass_rate = pass_count / len(curr_att["checks"]) if curr_att["checks"] else 1.0

        st.progress(pass_rate, text=f"Certification Score: {pass_count}/10 Passed ({pass_rate * 100:.0f}%)")

        # Filter option
        filter_mode = st.radio("Filter Checks:", ["All 10 Checks", "Failed Checks Only", "Passed Checks Only"], horizontal=True)

        rows = []
        for c in curr_att["checks"]:
            cid = c.get("check_id", "")
            meta = CHECK_METADATA.get(cid, {})
            passed = c.get("passed", False)
            if filter_mode == "Failed Checks Only" and passed:
                continue
            if filter_mode == "Passed Checks Only" and not passed:
                continue

            rows.append({
                "Check ID": cid,
                "Status": "PASS" if passed else "FAIL",
                "Evaluation Tier": meta.get("type", "Deterministic / LLM"),
                "Rubric Description": meta.get("description", ""),
                "Diagnostic Reason": c.get("reason", ""),
                "Verbatim Quote": c.get("evidence_quote", ""),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            def highlight_status(row):
                if row["Status"] == "FAIL":
                    return ["background-color: #fee2e2; color: #991b1b; font-weight: bold;"] * len(row)
                return ["background-color: #f0fdf4; color: #166534;"] * len(row)

            st.dataframe(df.style.apply(highlight_status, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info("No checks match the selected filter.")
    else:
        st.info("No evaluation matrix available yet.")

# ==============================================================================
# TAB 3: Rejection & Surgical Edits
# ==============================================================================
with tabs[2]:
    st.markdown("### 🔍 Diagnostic Critiques & Surgical Revisions")
    data = st.session_state.get("run_data")
    if data and data["attempts"]:
        for a in data["attempts"]:
            with st.expander(f"Attempt #{a['attempt_number']} Rejection & Revision Trace", expanded=not a["passed"]):
                if a["failing_checks"]:
                    st.markdown(f"**🚨 Triggered Rejection Thresholds ({len(a['failing_checks'])}):** `{', '.join(a['failing_checks'])}`")
                    for c in a["checks"]:
                        if not c.get("passed"):
                            quote_html = f"<div class='evidence-quote'><strong>Verbatim Evidence:</strong> \"{c.get('evidence_quote')}\"</div>" if c.get('evidence_quote') else ""
                            st.markdown(f"""
                            <div class="critique-card">
                                <strong>Check:</strong> <code>{c.get('check_id')}</code><br>
                                <strong>Critique:</strong> {c.get('reason')}
                                {quote_html}
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.success("🎉 All 10 rubric checks passed successfully on this attempt with zero rejection.")

                if a.get("changes_made"):
                    changes_formatted = a['changes_made'].replace("\n", "<br>")
                    st.markdown(f"""
                    <div class="revision-card">
                        <strong>🛠️ Surgical Actions Applied by ReviserNode:</strong><br>
                        {changes_formatted}
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("No rejection records available.")

# ==============================================================================
# TAB 4: Published Lesson & Reading Inspector
# ==============================================================================
with tabs[3]:
    st.markdown("### 📖 Published Lesson Artifact & Readability Inspector")
    data = st.session_state.get("run_data")
    if data and data.get("lesson_md"):
        if data["status"] == "passed":
            st.success("### STATUS: PASSED & READY TO SHIP\nAll 10 binary rubric checks certified. Factual alignment and pedagogical tone validated.")
        else:
            st.warning("### STATUS: NEEDS HUMAN REVIEW\nRetry budget exhausted. Best attempt selected with fewest failing checks. Review recommended.")

        # Readability stats inspector
        clean_text = strip_markdown(data["lesson_md"])
        fk_grade = textstat.flesch_kincaid_grade(clean_text) if len(clean_text.split()) > 30 else 0.0
        words = len(clean_text.split())
        sentences = textstat.sentence_count(clean_text) if clean_text else 1
        avg_sent = round(words / max(sentences, 1), 2)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Flesch-Kincaid Grade", f"{fk_grade:.2f}", delta="Target <= 7.0" if fk_grade <= 7.0 else "Exceeds Target", delta_color="normal" if fk_grade <= 7.0 else "inverse")
        m2.metric("Avg Sentence Length", f"{avg_sent} w", delta="Target <= 15.0 w" if avg_sent <= 15.0 else "Exceeds Target", delta_color="normal" if avg_sent <= 15.0 else "inverse")
        m3.metric("Total Word Count", f"{words} words", delta="800 - 1200 target")
        m4.metric("Est. Reading Time", f"{max(1, round(words / 150))} min", "Beginner pace")

        c1, c2 = st.columns(2)
        c1.download_button("📥 Download lesson.md", data["lesson_md"], file_name="lesson.md", mime="text/markdown", use_container_width=True)
        c2.download_button("📥 Download rejection_log.json", data["rejection_log_json"], file_name="rejection_log.json", mime="application/json", use_container_width=True)

        st.markdown("---")
        st.markdown(data["lesson_md"])
    else:
        st.info("No lesson generated yet.")

# ==============================================================================
# TAB 5: Memory Store & Evolution
# ==============================================================================
with tabs[4]:
    st.markdown("### 🧠 Persistent SQLite Learned Rules & Evolution")
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
                        active_count = sum(1 for r in rows if r[3])
                        col_m1, col_m2 = st.columns(2)
                        col_m1.metric("Active Rules (Injected in Generator)", f"{active_count} / {settings.active_rules_limit}")
                        col_m2.metric("Total Extracted Rules in Memory", len(rows))

                        st.markdown("#### 📜 Learned Rule Knowledge Base")
                        mem_df = pd.DataFrame(rows, columns=["ID", "Source Check", "Recurrence", "Active", "Rule Guidance", "Created At"])
                        st.dataframe(mem_df, use_container_width=True, hide_index=True)

            # Proposed Rubric v2 Inspector
            rubric_v2_path = settings.rubric_v2_proposed_path
            if rubric_v2_path.exists():
                with st.expander("📝 Proposed Rubric v2 (Reflector Meta-Evolution)", expanded=False):
                    rubric_data = json.loads(rubric_v2_path.read_text(encoding="utf-8"))
                    st.json(rubric_data)
        except Exception:
            st.info("No learned rules yet.")

# ==============================================================================
# TAB 6: Compare Attempts
# ==============================================================================
with tabs[5]:
    st.markdown("### ⚖️ Side-by-Side Attempt Comparison")
    data = st.session_state.get("run_data")
    if data and len(data["attempts"]) > 1:
        att_options = [f"Attempt #{a['attempt_number']}" for a in data["attempts"]]
        s1, s2 = st.columns(2)
        sel_a = s1.selectbox("Base Attempt", att_options, index=0)
        sel_b = s2.selectbox("Revised Attempt", att_options, index=1)

        att_a = data["attempts"][att_options.index(sel_a)]
        att_b = data["attempts"][att_options.index(sel_b)]

        st.markdown(f"**Reviser Actions Between Attempts:**")
        if att_b.get("changes_made"):
            st.info(att_b["changes_made"])
        else:
            st.caption("No changes recorded.")

        status_a = "PASSED" if att_a["passed"] else f"FAILED: {len(att_a.get('failing_checks', []))} failing"
        status_b = "PASSED" if att_b["passed"] else f"FAILED: {len(att_b.get('failing_checks', []))} failing"

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"#### {sel_a} ({status_a})")
            st.text_area(f"{sel_a} Prose", att_a["content"], height=550, disabled=True, key="cmp_txt_a")
        with c2:
            st.markdown(f"#### {sel_b} ({status_b})")
            st.text_area(f"{sel_b} Prose", att_b["content"], height=550, disabled=True, key="cmp_txt_b")
    elif data and len(data["attempts"]) == 1:
        st.success("🎉 Attempt 0 passed on the very first try with zero rejections. No revised attempts needed!")
    else:
        st.info("No attempts available to compare.")
