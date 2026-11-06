# Loom Video Demonstration Script (15–20 Minutes)

This script provides a structured guide for recording the 15–20 minute face-visible Loom demonstration for the **GenAI Engineer - Content Systems** assessment.

---

## Video Outline & Time Allocation

| Section | Timestamp | Focus Topic | Key Visuals / Actions |
| :--- | :--- | :--- | :--- |
| **1. Introduction & Context** | 00:00 – 02:30 | Mission, candidate background, learner persona | Face on camera, slide/README with persona description |
| **2. Architecture Walkthrough** | 02:30 – 06:00 | LangGraph state machine, 10-check hybrid rubric | Mermaid diagram, `src/graph.py`, `data/rubric_v1.json` |
| **3. Live End-to-End Pipeline Run** | 06:00 – 10:00 | Standard autonomous run from topic to passing lesson | Terminal running `python main.py`, Rich UI progress |
| **4. Deliberate Fault Catch Demo** | 10:00 – 14:00 | Fault injection catching an error & surgical revision | Running `python main.py --inject-fault hallucination` |
| **5. Test Suite & Evaluator Catch Rate**| 14:00 – 16:30 | Catch rate on 8 bad lessons + 1 golden lesson | Running `pytest tests/test_evaluator.py -v -s` |
| **6. Memory Store & Self-Evolution** | 16:30 – 18:30 | SQLite persistence, rule extraction & evolution | Running `python main.py --demo-evolution`, inspecting SQLite |
| **7. Conclusion & Deliverables** | 18:30 – 20:00 | Final wrap-up and submission deliverables | Viewing `outputs/lesson.md` and `outputs/rejection_log.md` |

---

## Detailed Speaking Script

### 1. Introduction & Context (00:00 – 02:30)
* **On Camera**: "Hello! My name is [Your Name], and this is my submission for the GenAI Engineer - Content Systems assessment.
* Today, we are not looking at a one-line prompt that generates generic text. We are looking at an **autonomous, self-evaluating content system** that generates educational material, grades its own work against hard pass/fail standards, makes surgical revisions, and learns from its failures over time.
* **Our Target Learner Persona**: A 12th-grade high school graduate from India from a non-English-medium background with zero technical knowledge who wants to enter AI. Every design decision—from our Flesch-Kincaid grade threshold to our college chatbot worked example—is tuned specifically for this student."

### 2. Architecture & Design Choices (02:30 – 06:00)
* **Show Screen**: Open `docs/DESIGN.md` and the Mermaid diagram in `README.md`.
* **Talking Points**:
  - "The system is built on LangGraph as a cyclic state machine with 7 specialized nodes: Grounder, Planner, Generator, Evaluator, Router, Reviser, and Reflector."
  - "Notice our **Hybrid Evaluator**:
    1. Quantitative checks (reading level $\le$ grade 7, sentence length $\le$ 15 words, glossary coverage, and exact quiz structure) are computed deterministically in Python with markdown stripped.
    2. Qualitative pedagogy (accuracy against the Lewis et al. fact pack, conceptual flow, absence of Western idioms, intuitive analogies, and Indian-context examples) is judged by a separate, higher-tier LLM.
    3. Crucially, when the judge detects a violation, it must provide a **verbatim evidence quote** from the lesson draft. Our Python code programmatically verifies that the quote exists in the text. If the judge hallucinates a quote, it is rejected!"
  - "Show `data/fact_pack.json` grounded in the Lewis et al. (2020) NeurIPS paper and `data/rubric_v1.json`."

### 3. Live End-to-End Pipeline Run (06:00 – 10:00)
* **Action**: In the terminal, run:
  ```bash
  python main.py
  ```
* **Talking Points**:
  - Point to the Rich terminal output showing:
    - Grounder loading facts and memory rules.
    - Planner generating the 8-concept checklist.
    - Generator drafting the lesson.
    - Evaluator running all 10 checks with the color-coded pass/fail grid.
  - "Here we see the system evaluate each check. All 10 checks pass, the lesson is approved, and the output is saved to `outputs/lesson.md`."

### 4. Live Fault Injection Demonstration (10:00 – 14:00)
* **Action**: In the terminal, run:
  ```bash
  python main.py --inject-fault hallucination
  ```
* **Talking Points**:
  - "Now let's test the rigor of our evaluator by deliberately injecting a critical technical misconception: claiming that RAG retrains the model's neural network weights on your documents."
  - Watch Attempt 0 fail:
    - "Look at the terminal: check `accuracy` failed with a bright red cross!"
    - "Notice the verbatim evidence quote caught by the evaluator: *'RAG works by retraining the underlying neural network weights on your private documents.'*"
  - Watch the Reviser kick in:
    - "Instead of wiping the entire document, the Reviser makes a surgical fix to that exact paragraph."
  - Watch Attempt 1 pass:
    - "In Attempt 1, the check passes, and the rejection log documents exactly what failed, the evidence quote, and what changed!"
  - Open `outputs/rejection_log.md` to show the clean markdown audit trail.

### 5. Evaluator Test Suite & Catch Rate Table (14:00 – 16:30)
* **Action**: In the terminal, run:
  ```bash
  pytest tests/test_evaluator.py -v -s
  ```
* **Talking Points**:
  - "To prove the evaluator isn't a fluke, we have an extensive automated benchmark in `tests/bad_lessons/` with 8 hand-crafted test lessons violating exactly one check each, plus 1 golden lesson."
  - Highlight the terminal output:
    - "Notice this catch-rate table. 100% of bad lessons are caught by their respective check, and the golden lesson passes with 10/10 checks green."

### 6. Memory Store & Self-Evolution (`--demo-evolution`) (16:30 – 18:30)
* **Action**: In the terminal, run:
  ```bash
  python main.py --demo-evolution
  ```
* **Talking Points**:
  - "Here is where the system truly becomes self-evolving. Our SQLite store in `data/memory.db` tracks failure patterns across runs."
  - "The Reflector analyzes recurring failure modes, generates actionable learned rules (such as *'Always introduce chunking before vector search'*), and injects them into the Generator prompt on future runs."
  - "Notice that the system caps active rules at 5 to prevent prompt bloat and proposes rubric improvements into `data/rubric_v2_proposed.json` with a changelog without destructively mutating the active standard."

### 7. Conclusion & Submission Deliverables (18:30 – 20:00)
* **Action**: Open `outputs/lesson.md` and review the final generated lesson.
* **Talking Points**:
  - "Let's review the final generated lesson: simple vocabulary, open-book exam analogy, Indian college admissions chatbot example, 8 key concepts covered, and exactly 3 self-check questions."
  - "All deliverables—the GitHub repo, complete documentation, test suite, and final lesson document—are fully ready. Thank you!"
