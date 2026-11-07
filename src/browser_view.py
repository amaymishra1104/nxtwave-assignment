"""Interactive Browser Viewer for Lesson Generator and Evaluator.

Generates a standalone, beautiful HTML dashboard combining:
1. The rendered pedagogical lesson
2. The 10-check rubric pass/fail matrix
3. Rejection & revision audit log with verbatim quotes
4. SQLite memory store telemetry and learned rules

Opens automatically in the default web browser.
"""

import json
from pathlib import Path
import sqlite3
import webbrowser
from typing import Optional

from src.config import settings


def generate_html_dashboard(run_id: Optional[str] = None) -> Path:
    """Build a rich, self-contained HTML dashboard from latest outputs and telemetry."""
    outputs_dir = settings.output_dir
    lesson_path = outputs_dir / "lesson.md"
    rejection_json_path = outputs_dir / "rejection_log.json"
    db_path = settings.database_path

    # Fallback to submission/ if outputs/ is empty
    if not lesson_path.exists() and (Path("submission") / "lesson.md").exists():
        lesson_path = Path("submission") / "lesson.md"
        rejection_json_path = Path("submission") / "rejection_log.json"

    lesson_md = lesson_path.read_text(encoding="utf-8") if lesson_path.exists() else "# No lesson generated yet."
    
    rejection_data = {}
    if rejection_json_path.exists():
        try:
            rejection_data = json.loads(rejection_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read learned rules from SQLite
    learned_rules = []
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, source_check_id, failure_count, active, rule_text FROM learned_rules ORDER BY failure_count DESC, id ASC")
            learned_rules = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception:
            pass

    status = rejection_data.get("status", "passed").upper()
    current_run_id = rejection_data.get("run_id", run_id or "latest_run")
    attempts_count = rejection_data.get("attempts_count", len(rejection_data.get("rejection_log", [])))

    status_badge_color = "bg-emerald-500" if status == "PASSED" else "bg-amber-500"
    status_label = "PASSED & READY TO SHIP" if status == "PASSED" else "NEEDS HUMAN REVIEW"

    # HTML template with Tailwind and Marked
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Autonomous Lesson & Evaluation Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
    code, pre {{ font-family: 'JetBrains Mono', monospace; }}
    .prose h1 {{ font-size: 1.875rem; font-weight: 800; color: #0f172a; margin-top: 1.5rem; margin-bottom: 0.75rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
    .prose h2 {{ font-size: 1.5rem; font-weight: 700; color: #1e293b; margin-top: 1.5rem; margin-bottom: 0.75rem; }}
    .prose h3 {{ font-size: 1.25rem; font-weight: 600; color: #334155; margin-top: 1.25rem; margin-bottom: 0.5rem; }}
    .prose p {{ line-height: 1.75; color: #334155; margin-bottom: 1rem; font-size: 1.05rem; }}
    .prose ul, .prose ol {{ margin-left: 1.5rem; margin-bottom: 1rem; color: #334155; }}
    .prose li {{ margin-bottom: 0.35rem; }}
    .prose blockquote {{ border-left: 4px solid #3b82f6; background-color: #eff6ff; padding: 0.75rem 1rem; border-radius: 0.375rem; margin: 1rem 0; font-style: italic; }}
    .prose hr {{ margin: 2rem 0; border-color: #cbd5e1; }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
  <!-- Top Navigation Header -->
  <header class="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50 shadow-md">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap justify-between items-center gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center font-extrabold text-lg text-white shadow-inner">AG</div>
        <div>
          <h1 class="font-bold text-base tracking-tight">Autonomous Lesson Generation & Evaluator</h1>
          <p class="text-xs text-slate-400">Target: 12th-Grade Graduate (India, Non-English Medium) • LangGraph State Machine</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold text-white {status_badge_color}">
          <span class="w-2 h-2 mr-1.5 rounded-full bg-white animate-pulse"></span>
          {status_label}
        </span>
        <span class="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded border border-slate-700">Run: <code class="text-blue-400">{current_run_id}</code></span>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Tab Controls -->
    <div class="border-b border-slate-200 mb-8">
      <nav class="-mb-px flex space-x-8" aria-label="Tabs">
        <button onclick="switchTab('lesson')" id="tab-btn-lesson" class="tab-btn border-blue-600 text-blue-600 whitespace-nowrap py-3 px-1 border-b-2 font-semibold text-sm flex items-center gap-2">
          <span>📖</span> Published Lesson
        </button>
        <button onclick="switchTab('rubric')" id="tab-btn-rubric" class="tab-btn border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 whitespace-nowrap py-3 px-1 border-b-2 font-semibold text-sm flex items-center gap-2">
          <span>🎯</span> 10-Check Evaluation Matrix
        </button>
        <button onclick="switchTab('rejection')" id="tab-btn-rejection" class="tab-btn border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 whitespace-nowrap py-3 px-1 border-b-2 font-semibold text-sm flex items-center gap-2">
          <span>🔍</span> Rejection & Revision Telemetry ({attempts_count} Attempts)
        </button>
        <button onclick="switchTab('memory')" id="tab-btn-memory" class="tab-btn border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 whitespace-nowrap py-3 px-1 border-b-2 font-semibold text-sm flex items-center gap-2">
          <span>🧠</span> SQLite Memory & Learned Rules ({len(learned_rules)})
        </button>
      </nav>
    </div>

    <!-- TAB 1: Published Lesson -->
    <div id="tab-content-lesson" class="tab-content">
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 sm:p-12">
        <div class="mb-6 pb-6 border-b border-slate-100 flex flex-wrap justify-between items-center text-xs text-slate-500 gap-2">
          <div class="flex items-center gap-2">
            <span class="font-medium text-slate-700">Topic:</span> Introduction to RAG (Retrieval-Augmented Generation)
          </div>
          <div class="flex items-center gap-3">
            <span class="bg-blue-50 text-blue-700 px-2.5 py-1 rounded-md font-medium border border-blue-100">Grade &le; 7 Reading Level</span>
            <span class="bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-md font-medium border border-emerald-100">Zero Unexplained Jargon</span>
            <span class="bg-purple-50 text-purple-700 px-2.5 py-1 rounded-md font-medium border border-purple-100">India Scenario</span>
          </div>
        </div>
        <div id="lesson-markdown-render" class="prose max-w-none"></div>
      </div>
    </div>

    <!-- TAB 2: Evaluation Matrix (10 Checks) -->
    <div id="tab-content-rubric" class="tab-content hidden">
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="p-6 bg-slate-900 text-white">
          <h2 class="text-lg font-bold">10-Check Pedagogical Rubric Matrix</h2>
          <p class="text-xs text-slate-400 mt-1">Hybrid architecture: Deterministic Code (quantitative readability & glossary parsing) + Independent LLM Judge (qualitative pedagogical grading).</p>
        </div>
        <div class="divide-y divide-slate-200">
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">1</span> accuracy</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge (Fact Pack Anchor)</div>
            <div class="text-sm text-slate-600 md:col-span-2">Factual fidelity to Lewis et al. (2020). Verifies model weights stay frozen and RAG never modifies weights.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">2</span> what_why_how</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Comprehensive coverage answering What RAG is, Why models need it (hallucination reduction), and How it functions.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">3</span> key_points</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Explicit coverage of all 8 core concepts: retrieval, embeddings, vector database, chunking, prompt augmentation, generation, hallucination reduction, limitations.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">4</span> jargon_defined</div>
            <div class="text-xs text-emerald-700 font-medium">Deterministic + LLM Hybrid</div>
            <div class="text-sm text-slate-600 md:col-span-2">All 12 glossary terms defined on initial introduction with zero prerequisite technical knowledge assumed.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">5</span> reading_level</div>
            <div class="text-xs text-emerald-700 font-medium">Deterministic Code (Pure Math)</div>
            <div class="text-sm text-slate-600 md:col-span-2">Markdown stripped &rarr; Flesch-Kincaid Grade Level &le; 7.0 AND Average Sentence Length &le; 15.0 words. Zero partial credit.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">6</span> no_idioms</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Zero Western colloquialisms or opaque cultural idioms (e.g. 'bite the bullet', 'silver bullet', 'hit the ground running').</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">7</span> worked_example</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Concrete 3-step walkthrough set in an Indian student context (e.g. college admission chatbot reading a notice PDF circular).</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">8</span> analogy</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Intuitive comparison between closed-book memory tests and open-book exam retrieval introduced early in the lesson.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">9</span> coherent_flow</div>
            <div class="text-xs text-purple-700 font-medium">LLM Judge</div>
            <div class="text-sm text-slate-600 md:col-span-2">Logical pedagogical progression: Problem (limits of memory) &rarr; Solution (RAG) &rarr; Mechanics &rarr; Limitations.</div>
          </div>
          <div class="p-4 sm:p-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-center hover:bg-slate-50 transition">
            <div class="font-bold text-slate-900 flex items-center gap-2"><span class="w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs flex items-center justify-center font-bold">10</span> wrap_up</div>
            <div class="text-xs text-emerald-700 font-medium">Deterministic + LLM Hybrid</div>
            <div class="text-sm text-slate-600 md:col-span-2">Dedicated section with heading '## Self-Check' containing exactly three numbered practice questions.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: Rejection & Revision Telemetry -->
    <div id="tab-content-rejection" class="tab-content hidden">
      <div class="space-y-6" id="rejection-attempts-container">
        <!-- Rendered via JS from rejection_data -->
      </div>
    </div>

    <!-- TAB 4: SQLite Memory & Rules -->
    <div id="tab-content-memory" class="tab-content hidden">
      <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden p-6">
        <div class="mb-6">
          <h2 class="text-lg font-bold text-slate-900">SQLite Memory Store (`data/memory.db`)</h2>
          <p class="text-xs text-slate-500">Autonomous self-evolution across runs: extracts recurring failures, updates recurrence frequencies, and caps top 5 active rules injected into future generation prompts.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200 text-sm">
            <thead class="bg-slate-50">
              <tr>
                <th class="px-4 py-3 text-left font-semibold text-slate-700">ID</th>
                <th class="px-4 py-3 text-left font-semibold text-slate-700">Source Check</th>
                <th class="px-4 py-3 text-center font-semibold text-slate-700">Recurrence Count</th>
                <th class="px-4 py-3 text-center font-semibold text-slate-700">Status</th>
                <th class="px-4 py-3 text-left font-semibold text-slate-700">Learned Rule Text</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-200">
              {''.join([f'''
              <tr class="hover:bg-slate-50">
                <td class="px-4 py-3 font-mono text-xs text-slate-500">#{r['id']}</td>
                <td class="px-4 py-3 font-semibold text-slate-800"><span class="bg-slate-100 text-slate-700 px-2 py-0.5 rounded text-xs">{r['source_check_id']}</span></td>
                <td class="px-4 py-3 text-center font-bold text-blue-600">{r['failure_count']}</td>
                <td class="px-4 py-3 text-center">
                  <span class="inline-flex px-2 py-0.5 rounded text-xs font-semibold {'bg-emerald-100 text-emerald-800' if r['active'] else 'bg-slate-100 text-slate-600'}">
                    {'ACTIVE' if r['active'] else 'INACTIVE'}
                  </span>
                </td>
                <td class="px-4 py-3 text-slate-700 text-xs">{r['rule_text']}</td>
              </tr>
              ''' for r in learned_rules]) if learned_rules else '<tr><td colspan="5" class="p-6 text-center text-slate-500">No learned rules in database yet.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>

  <script>
    // Tab switching logic
    function switchTab(tabName) {{
      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.remove('border-blue-600', 'text-blue-600');
        btn.classList.add('border-transparent', 'text-slate-500');
      }});
      document.querySelectorAll('.tab-content').forEach(content => {{
        content.classList.add('hidden');
      }});

      const selectedBtn = document.getElementById('tab-btn-' + tabName);
      const selectedContent = document.getElementById('tab-content-' + tabName);
      if (selectedBtn && selectedContent) {{
        selectedBtn.classList.remove('border-transparent', 'text-slate-500');
        selectedBtn.classList.add('border-blue-600', 'text-blue-600');
        selectedContent.classList.remove('hidden');
      }}
    }}

    // Render Lesson Markdown
    const rawLessonMarkdown = {json.dumps(lesson_md)};
    document.getElementById('lesson-markdown-render').innerHTML = marked.parse(rawLessonMarkdown);

    // Render Rejection Data
    const rejectionData = {json.dumps(rejection_data)};
    const container = document.getElementById('rejection-attempts-container');
    if (rejectionData && rejectionData.rejection_log) {{
      container.innerHTML = rejectionData.rejection_log.map(a => {{
        const passed = a.evaluation ? a.evaluation.passed : false;
        const failingChecks = a.evaluation ? a.evaluation.failing_checks : [];
        const details = (a.evaluation && a.evaluation.failed_check_details) ? a.evaluation.failed_check_details : [];
        
        return `
          <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
              <div class="flex items-center gap-3">
                <span class="font-bold text-slate-900 text-base">Attempt #${{a.attempt_number}}</span>
                <span class="text-xs text-slate-500 font-mono">${{a.timestamp || ''}}</span>
              </div>
              <span class="px-2.5 py-1 rounded text-xs font-bold ${{passed ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}}">
                ${{passed ? 'PASSED (10/10)' : 'FAILED (' + failingChecks.length + ' FAILING)'}}
              </span>
            </div>
            
            <div class="p-6 space-y-4">
              ${{details.length > 0 ? `
                <div class="space-y-3">
                  <h4 class="text-xs font-bold tracking-wider text-rose-700 uppercase">Diagnostic Rejection Critique</h4>
                  ${{details.map(d => `
                    <div class="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-lg text-sm text-slate-800 space-y-1.5">
                      <div class="font-bold text-rose-900 flex items-center gap-1.5">
                        <span>✖</span> Check: <code>${{d.check_id}}</code>
                      </div>
                      <p class="text-slate-700">${{d.reason}}</p>
                      ${{d.evidence_quote ? `
                        <div class="text-xs text-amber-900 bg-amber-50/80 p-2 rounded border border-amber-200 mt-2 italic font-mono">
                          <strong>Evidence Quote:</strong> "${{d.evidence_quote}}"
                        </div>
                      ` : ''}}
                    </div>
                  `).join('')}}
                </div>
              ` : '<div class="text-emerald-700 font-semibold text-sm flex items-center gap-2"><span>✔</span> All 10 hard pass/fail rubric checkpoints met cleanly.</div>'}}

              ${{a.changes_made ? `
                <div class="mt-4 pt-4 border-t border-slate-100">
                  <h4 class="text-xs font-bold tracking-wider text-blue-700 uppercase mb-2">Surgical Changes Applied by ReviserNode</h4>
                  <div class="bg-blue-50 border border-blue-200 rounded-lg p-3.5 text-xs text-blue-900 whitespace-pre-wrap font-mono">${{a.changes_made}}</div>
                </div>
              ` : ''}}
            </div>
          </div>
        `;
      }}).join('');
    }} else {{
      container.innerHTML = '<div class="bg-white p-8 text-center text-slate-500 rounded-2xl border border-slate-200">No rejection records found.</div>';
    }}
  </script>
</body>
</html>
"""

    html_file = outputs_dir / "view.html"
    html_file.write_text(html_content, encoding="utf-8")
    return html_file


def open_dashboard_in_browser(run_id: Optional[str] = None):
    """Generate HTML dashboard and launch default system web browser."""
    html_file = generate_html_dashboard(run_id=run_id)
    url = html_file.resolve().as_uri()
    print(f"\n[Browser Dashboard Generated]: {html_file.resolve()}")
    print(f"Opening in browser: {url}\n")
    webbrowser.open(url)
    return html_file


if __name__ == "__main__":
    import sys
    rid = sys.argv[1] if len(sys.argv) > 1 else None
    open_dashboard_in_browser(run_id=rid)
