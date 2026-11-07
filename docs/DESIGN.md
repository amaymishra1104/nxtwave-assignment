# System Architecture & Design Document

## 1. Problem Statement & Mission
In educational content generation for AI careers, generative AI models frequently fail beginners by either:
1. Writing dense academic prose packed with undefined technical jargon and foreign idioms.
2. Hallucinating false technical claims (e.g., claiming RAG retrains neural network weights).
3. Lacking interactive pedagogical structure (worked examples, analogies, check-for-understanding quizzes).

Our mission is to build an autonomous, self-evaluating content system that produces a beginner lesson on **"Introduction to RAG (Retrieval-Augmented Generation)"** for a **12th-grade graduate from India with a non-English-medium schooling background and limited English vocabulary**. The system must evaluate its own output against hard binary pass/fail standards, perform surgical self-corrections, and continuously evolve across runs through persistent memory.

---

## 2. Target Learner Persona
* **Demographic**: 17–19 year old high-school graduate in India.
* **Schooling**: Non-English medium (state board / vernacular primary education).
* **Vocabulary**: Simple English words; struggles with complex sentence clauses, Western idioms, and corporate jargon.
* **Technical Background**: Zero programming or machine learning background.
* **Goal**: Aspires to enter the burgeoning Indian AI workforce and needs clear, intuitive mental models.

---

## 3. High-Level Architecture (LangGraph State Machine)
The pipeline is modeled as a cyclic state machine built on LangGraph:

```
[User Input]
     │
     ▼
[Grounder] ──► Loads fact_pack.json, glossary.json, and top learned_rules
     │
     ▼
[Planner]  ──► Generates must-cover checklist & India-context lesson outline
     │
     ▼
[Generator] ──► Drafts 800–1200 word Markdown lesson (with learned rules injected)
     │
[Fault Injector] (Optional CLI hook on Attempt 0 for live demonstration)
     │
     ▼
[Evaluator] ──► HYBRID: Deterministic Code + LLM Judge (with Verbatim Quote Verification)
     │
     ▼
  [Router]
     ├──► [All 10 Passed] ───────────────────────────┐
     ├──► [Fail & Retries < 2] ──► [Reviser] ──► (Loop to Evaluator)
     └──► [Fail & Retries >= 2] ──► [Flag: NEEDS_HUMAN_REVIEW] (Select best attempt) ──┐
                                                                                       │
                                                                                       ▼
                                                                                 [Reflector]
                                                                                       │
                                                                                       ▼
                                                                               [Outputs & Memory]
```

### Node Responsibilities & Justifications
1. **Grounder**: Decouples domain truth from the LLM prompt. By loading verified facts from the Lewis et al. (2020) NeurIPS paper and official documentation, the evaluator has an external, immutable source of truth.
2. **Planner**: Enforces structural completeness before generation begins. Produces the 8 mandatory concept targets (retrieval, embeddings, vector database, chunking, prompt augmentation, generation, hallucination reduction, limitations) and outlines India-centric contexts.
3. **Generator**: Focuses purely on creative pedagogical drafting adhering to constraints, active learned rules, and target reading level ($FK \le 7$, avg sentence length $\le 15$).
4. **Evaluator (Hybrid)**:
   - **Deterministic Code**: Evaluates quantitative metrics that LLMs evaluate poorly (exact sentence lengths, readability formulas, verbatim string definitions at first use, markdown structure, exact quiz question counts).
   - **LLM Judge**: Evaluates qualitative pedagogy (factual alignment against ground facts, absence of idioms, intuitive analogy, conceptual flow). Requires **verbatim evidence quotes** for any cited violation.
5. **Router**: Deterministic branching logic ensuring the loop strictly terminates within 2 retries.
6. **Reviser**: Makes **surgical, targeted modifications** to the failing parts of the lesson rather than completely rewriting the text. This preserves previously passing sections and saves latency/cost.
7. **Reflector**: Inspects run logs, updates the SQLite memory store, extracts recurring failure patterns into new learned rules, and proposes structured updates in `rubric_v2_proposed.json` without overwriting the active rubric.

---

## 4. Key Design Decisions & Trade-Offs

### A. Independent Models for Generator and Judge
* **Decision**: We configure separate models (e.g., `GENERATOR_MODEL=gemini-2.5-flash`, `JUDGE_MODEL=gemini-2.5-pro`) and distinct temperatures (0.7 for generation, 0.2 for evaluation).
* **Rationale**: Using the same model to both generate and evaluate introduces self-confirmation bias. A higher-tier model with low temperature acts as an objective, strict grader.

### B. Verbatim Evidence Quote Verification
* **Decision**: Whenever the LLM Judge flags a violation, it must return an `evidence_quote` copied verbatim from the lesson draft. Python code immediately verifies that `evidence_quote in lesson_text`. If the judge fabricates a quote, the check is treated as a judge error and retried. (For missing-element failures, empty quotes are permitted and not retried).
* **Rationale**: Eliminates judge hallucinations and provides transparent, actionable proof in the rejection log.

### C. Markdown Stripping Before Readability Calculation
* **Decision**: Markdown syntax (headers, bullets, code fences, bold marks, hyperlinks) is stripped into clean prose before computing Flesch-Kincaid Grade Level and sentence word counts.
* **Rationale**: Punctuation and header tokens artificially inflate sentence counts and distort syllable ratios if measured raw.

### D. Surgical Revisions vs. Full Rewrites
* **Decision**: The Reviser receives the failed check IDs, reasons, and evidence quotes, and is instructed to patch only the offending paragraphs.
* **Rationale**: Full regenerations often introduce new regressions into sections that had already passed. Targeted editing converges faster and produces clear "what changed" logs.

### E. Persistent Memory & Safe Self-Evolution
* **Decision**: Run telemetry, attempts, check failures, and learned rules persist in SQLite (`data/memory.db`). The Reflector suggests rubric refinements to `data/rubric_v2_proposed.json` with a detailed changelog.
* **Rationale**: Autonomous agents must not silently mutate their own evaluation standards in production. Human-in-the-loop governance requires proposed changes to be reviewed while prompt rules can evolve dynamically within a capped threshold (top 5 active rules).

---

## 5. Best Attempt Selection Strategy
If an attempt fails and the retry budget is exhausted ($retries \ge 2$), the system does not crash or abort. Instead, it selects the **best attempt**—defined deterministically as the attempt with the **fewest failing checks**—and ships it flagged as `status: NEEDS_HUMAN_REVIEW`.

---

## 6. Check Changes and Why (Measurement Precision & Typographical Robustness)

During development and rigorous empirical testing between Milestone 2 and Milestone 6, specific refinements were made to the deterministic evaluation suite. These adjustments were not made to increase leniency or soften standards; rather, they corrected mechanical tokenization artifacts, typographical boundary errors, and parser blindspots so that measurement accurately reflects instructional quality.

| Check Affected | Pre-Fix Behavior | Root Cause | Engineering Fix Applied | Effect on Golden Lesson Scores |
| :--- | :--- | :--- | :--- | :--- |
| **`reading_level`** (`strip_markdown`) | Raw markdown headings like `## What is RAG` lacked terminal periods. | Standard sentence tokenizers (`nltk` / `textstat`) merged the heading text with the first sentence of the following paragraph into a single runaway sentence (e.g., `What is RAG Imagine you are...`), falsely reporting sentences $>25$ words and inflating syllable-per-sentence ratios. | `strip_markdown()` now verifies if a markdown heading ends with terminal punctuation (`.`, `!`, `?`, `:`). If omitted, a period is appended during stripping before text metrics are computed. | Correctly segmented headings from introductory prose. Golden lesson sentence length shifted from 10.8 to 10.1 words; Flesch-Kincaid Grade Level shifted from 6.72 to 6.32 (both well within $\le 15.0$ and $\le 7.0$ limits). |
| **`jargon_defined`** (`check_glossary_coverage`) | Standalone title banners (e.g. `# Introduction to RAG`) were evaluated as Sentence 0 of the body prose. | A title is an introductory document label, not an explanatory paragraph. Flagging the title for not defining RAG inside the title itself produced a false-positive violation before the student even reached the introductory paragraph. | Markdown heading lines starting with `#` are excluded from the initial-use sentence queue. The glossary check strictly enforces that every technical term is defined upon its first appearance in body instructional text. | Golden lesson maintains 100% glossary coverage pass without false positive rejections on document headers. |
| **`jargon_defined`** (`check_glossary_coverage`) | Restricted definition cues to rigid copular strings (`is`, `are`, `means`, `defined as`). | Natural educational prose written for Indian high school students frequently introduces terms using conversational pedagogical phrasing (e.g., *"We call this technique Retrieval-Augmented Generation"*, *"which stands for..."*). | Expanded indicator matching to include pedagogical patterns (`call`, `called`, `short for`, `stands for`, `referred to as`) and permitted definitions in immediately adjacent introductory clauses. | Robustly validates clear, natural definitions without diluting the strict rule that no jargon may be used unexplained. |
| **`wrap_up`** & **`required_structure`** | Section title verification failed if the heading included a pedagogical contextual subtitle (e.g. `## Worked Example: College Admission Chatbot`). | The check regex expected exact literal string matches for `## Worked Example` without trailing contextual titles. | Adjusted section header matching to accept pedagogical colons and contextual suffixes (`## Worked Example: ...`, `## Real-World Scenario: ...`). | Preserves strict structural enforcement (Worked Example, Summary, Self-Check) while allowing descriptive educational labels. |
| **`reading_level`** (Diagnostic Feedback) | Evaluation failure reasons only supplied aggregate numbers (`FK 7.8 > 7.0`). | The Reviser agent was forced to guess which sentences inflated the grade, occasionally rewriting sections that were already simple. | The diagnostic engine now extracts and explicitly quotes every sentence exceeding 15 words and lists polysyllabic non-glossary words directly in the failure message passed to the Reviser. | Golden lesson score unaffected; live generation runs successfully converge from failed attempt 0 to fully passing attempt 1 or 2. |

---

## 7. Synthetic Fault Isolation in Telemetry & Memory Governance

### The Problem of Synthetic Contamination
In agentic self-evolution systems, developers frequently run integration tests with synthetic fault injection (e.g. `--inject-fault hallucination`) to verify that the Evaluator catches violations and the Reviser repairs them. If the Reflector naively processes every run, it will extract rules for synthetic flaws that the Generator never naturally committed. For example, injecting a false statement about fine-tuning neural network weights caused the Reflector to synthesize a rule specifically warning against retraining weights, despite the natural Generator having never made that mistake.

### Architectural Solution
1. **Schema Attribution (`runs.fault_injected`)**:
   The `runs` SQLite table now records a dedicated boolean flag `fault_injected INTEGER DEFAULT 0`. Any run triggered with `--inject-fault` is stamped with `fault_injected = 1`.
2. **Reflector Bypass**:
   When `state.fault_to_inject is not None`, the `ReflectorNode` persists the telemetry for auditable tracing but **skips all rule extraction and recurrence counting**.
3. **Failure Frequency Filtering**:
   The telemetry query `get_failure_frequency()` joins `check_results` with `runs` filtering `WHERE runs.fault_injected = 0`. Historical failure distributions and proposed rubric updates reflect exclusively organic model behavior.
4. **Purge of Injected Rules**:
   Any rules whose sole historical evidence derived from injected faults (such as the synthetic `accuracy` rule) have been purged from `learned_rules`.



