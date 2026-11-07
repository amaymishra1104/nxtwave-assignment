# Demo Video Recording Helper & Timing Suite

This directory contains `record_demo.py`, an automated presentation and recording utility designed to streamline screen-recording of the terminal during video demonstrations.

The script wraps existing CLI workflows via subprocesses without altering pipeline logic, prompts, rubric checks, or test fixtures (**additive only**).

---

## 1. Time Budget Schedule

The demo is budgeted across 5 core segments designed for an on-screen edited duration of **~11 minutes** (~11:30) with a raw live API recording budget of **~18 minutes**:

| # | Segment Name | Scope / CLI Command | Target (On-Screen) | Expected (Raw API) |
|---|--------------|---------------------|--------------------|--------------------|
| **1** | **Live end-to-end run** | `python main.py --topic "Introduction to RAG (Retrieval-Augmented Generation)"` | **3:00** (180s) | up to **4:00** (240s) |
| **2** | **Deliberate error caught** | `python main.py --topic "Introduction to RAG" --inject-fault hallucination` | **3:00** (180s) | up to **4:00** (240s) |
| **3** | **Evaluator catch-rate (live)** | `python tests/test_evaluator.py --live` | **2:00** (120s) | up to **5:00** (300s) |
| **4** | **Memory demo** | Inspect SQLite table -> `python main.py --topic "Introduction to RAG"` -> audit prompt | **2:00** (120s) | up to **3:00** (180s) |
| **5** | **Safe fallback replays** | `python main.py --replay examples/failing_then_passing_run` + `hallucination_fault_run` | **1:30** (90s) | up to **2:00** (120s) |
| **TOT** | **Full 5-Part Demo Session** | Complete multi-take recording | **~11:30** | **~18:00** |

---

## 2. Key Features

1. **Take-by-Take Control**:
   - Before each segment, displays a Rich title card with the viewer scope, target, and expected durations.
   - Waits for the presenter to press `[Enter]` before executing, allowing you to prepare audio and window framing.
   - Displays a completion card with the actual duration after the segment finishes.

2. **Live Elapsed-Time Clock**:
   - A real-time Rich status clock ticks in the footer during live execution (e.g. `⏳ Elapsed 01:42 / target 03:00`).
   - Automatically redraws without interfering with streamed terminal output.

3. **Narration Pauses (`--pause 3`)**:
   - Automatically pauses (default: 3 seconds) after key moments so the presenter has time to speak over the visual:
     - When the 10-check evaluation matrix table renders.
     - When an LLM Judge diagnostic critique with its **verbatim evidence quote** appears.
     - When the final shipping status card renders (`STATUS: PASSED & READY TO SHIP` or `NEEDS HUMAN REVIEW`).

4. **Timeout Guards (`--max-wait 360`)**:
   - If a live API call stalls or exceeds `--max-wait` (default: 360s), the helper cleanly terminates the subprocess tree (preventing orphan Python processes), notifies the presenter, and suggests using Segment 5 (safe fallback replay).

5. **Chapter Timeline Generation**:
   - For every recording session, writes a timestamped chapter timeline file in `demo/logs/timeline_<timestamp>.txt`.
   - Records segment names, start offsets, end offsets, durations, and statuses in `MM:SS` format from session start to facilitate post-production video editing.

6. **Offline Safe Replays**:
   - Segment 5 replays historical trace runs (`examples/failing_then_passing_run` and `examples/hallucination_fault_run`) with zero API calls and zero network dependency.

7. **Browser Walkthrough (`--browser`)**:
   - Automates Playwright to open `outputs/view.html`, cycling through the 4 dashboard tabs (Lesson, Rubric Matrix, Rejection Telemetry, and SQLite Memory) with 4-second pauses and automated screenshots saved to `demo/screenshots/`.

---

## 3. Usage Guide

### Pre-Flight Verification (0 API Calls)
Run before recording to verify environment credentials, SQLite database connectivity, replay health, and terminal width:
```bash
python demo/record_demo.py --check
```

### Record Individual Segments
```bash
# Segment 1: Live end-to-end lesson generation
python demo/record_demo.py --segment 1

# Segment 2: Deliberate error injection & self-correction
python demo/record_demo.py --segment 2

# Segment 3: Live evaluator 100% catch-rate benchmark
python demo/record_demo.py --segment 3

# Segment 4: SQLite memory inspection & prompt injection
python demo/record_demo.py --segment 4

# Segment 5: Offline fallback replay traces
python demo/record_demo.py --segment 5
```

### Record All Segments in One Session
```bash
python demo/record_demo.py --segment all --pause 3 --save-log
```
At the end of `--segment all`, a summary table displays the target vs actual duration for each segment, the total session time, and tailored video editing suggestions.

### Interactive Browser Walkthrough
```bash
python demo/record_demo.py --browser
```

### Available CLI Flags
- `--segment {1,2,3,4,5,all}`: Select specific segment or all sequentially.
- `--pause <sec>`: Pause length in seconds after evaluation tables, quotes, and status cards (default: `3.0`).
- `--max-wait <sec>`: Maximum timeout in seconds before aborting a live API process (default: `360`).
- `--save-log`: Tee all output to a timestamped log in `demo/logs/session_<timestamp>.log`.
- `--check`: Run pre-flight checks and display the budget table without making API calls.
- `--browser`: Run automated browser walkthrough of `outputs/view.html`.
- `--non-interactive`: Auto-advance title cards without waiting for Enter (for CI or automated testing).
- `--headless`: Run the browser walkthrough in headless mode.
