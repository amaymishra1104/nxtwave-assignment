"""Unit tests for deterministic code-based checks."""

import json
from pathlib import Path
import pytest

from src.checks.deterministic import (
    strip_markdown,
    calculate_sentence_metrics,
    check_reading_level,
    check_glossary_coverage,
    check_required_structure,
    check_quiz_structure,
)


def test_strip_markdown():
    """Verify markdown syntax stripping per Amendment 3."""
    sample = """
# Main Header
Here is a **bold** word and an *italic* word.
Check out [Google](https://google.com).
```python
def foo():
    return 42
```
* Bullet one
* Bullet two
1. Numbered item

> A blockquote here.
"""
    cleaned = strip_markdown(sample)
    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "```" not in cleaned
    assert "https://google.com" not in cleaned
    assert "bold word" in cleaned
    assert "Bullet one" in cleaned
    assert "Numbered item" in cleaned


def test_calculate_sentence_metrics():
    """Verify sentence length calculation on clean text."""
    text = "This is sentence one. This is sentence two. This is three."
    avg_len, words, sents = calculate_sentence_metrics(text)
    assert sents == 3
    assert words == 11
    assert round(avg_len, 2) == round(11 / 3, 2)


def test_reading_level_pass():
    """Verify beginner-friendly short text passes reading level check."""
    text = """
The cat sat on the mat. 
The dog ran in the park. 
The sun was bright and warm. 
We walked home with our friend. 
It was a very nice day. 
The birds sang sweet songs. 
Everyone was happy and calm. 
"""
    result = check_reading_level(text, max_grade=7.0, max_avg_sentence_len=15.0)
    assert result.passed is True
    assert result.check_id == "reading_level"


def test_reading_level_fail_complex_sentences():
    """Verify complex academic text with long sentences fails reading level check."""
    complex_text = """
The architectural manifestation of contemporary transformer-based neural mechanisms incorporates non-parametric epistemological repositories to circumvent the catastrophic forgetting paradigm inherent to monolithic parameterizations.
Furthermore, the retrieval mechanism synthesizes orthogonal hyperplanes within the latent manifold to approximate optimal semantic alignments across heterogeneous distributions.
Consequently, an empirical examination of this methodology reveals computational latency bottlenecks inherent in dense passage retrieval algorithms when scaling across extensive multi-modal corpora.
"""
    result = check_reading_level(complex_text, max_grade=7.0, max_avg_sentence_len=15.0)
    assert result.passed is False
    assert "exceeds" in result.reason or "difficult" in result.reason


def test_glossary_coverage_pass():
    """Verify text defining terms at first use passes."""
    glossary = {
        "Embedding": "A list of numbers that represents meaning.",
        "Chunking": "Breaking long text into small pieces.",
    }
    text = """
In this lesson, we use chunking. 
Chunking means breaking long text into small pieces. 
Then we convert each chunk into an embedding. 
An embedding is a list of numbers that represents text meaning. 
Later, the embedding helps us find relevant facts quickly.
"""
    result = check_glossary_coverage(text, glossary)
    assert result.passed is True


def test_glossary_coverage_fail():
    """Verify text using term without definition at first use fails and flags quote."""
    glossary = {
        "Embedding": "A list of numbers that represents meaning.",
    }
    text = """
We start by computing the embedding of every single passage in our corpus.
Then we send everything to our search tool.
"""
    result = check_glossary_coverage(text, glossary)
    assert result.passed is False
    assert "Embedding" in result.reason
    assert "embedding" in result.evidence_quote.lower()


def test_required_structure_pass_and_fail():
    """Verify required sections: title, headings, worked example, summary."""
    good_doc = """
# RAG Explained
## Section One
Here is basic content.
## Worked Example
A real-world example in action.
## Summary
Key takeaways here.
"""
    assert check_required_structure(good_doc).passed is True

    bad_doc = "Just some text without any headers or structure."
    assert check_required_structure(bad_doc).passed is False


def test_quiz_structure_counts_only_inside_self_check():
    """Amendment 2: Quiz check counts numbered items ONLY within Self-Check section."""
    doc_with_other_numbered_lists = """
# Lesson Title
## 1. How It Works
Here are steps in the body:
1. First step
2. Second step
3. Third step
4. Fourth step

## Worked Example
In this worked example:
1. Student asks question
2. System fetches answer

## Self-Check Questions
1. What is RAG?
2. Why do we chunk documents?
3. What is a vector database?
"""
    result = check_quiz_structure(doc_with_other_numbered_lists, required_count=3)
    assert result.passed is True
    assert "exactly 3" in result.reason


def test_quiz_structure_fails_when_count_is_not_three():
    """Verify failure when Self-Check section has fewer or more than 3 questions."""
    doc_with_two_questions = """
## Self-Check Questions
1. First question?
2. Second question?
"""
    result = check_quiz_structure(doc_with_two_questions, required_count=3)
    assert result.passed is False
    assert "found 2" in result.reason


def test_golden_lesson_passes_all_deterministic_checks():
    """Amendment 8: Golden lesson must pass all deterministic checks including glossary coverage."""
    lesson_path = Path("tests/good_lessons/good_rag_lesson.md")
    assert lesson_path.exists(), "Golden lesson file must exist"
    lesson_text = lesson_path.read_text(encoding="utf-8")

    # Load glossary
    glossary_path = Path("data/glossary.json")
    assert glossary_path.exists(), "Glossary must exist"
    glossary = json.loads(glossary_path.read_text(encoding="utf-8"))

    # 1. Reading level check
    reading_res = check_reading_level(lesson_text, max_grade=7.0, max_avg_sentence_len=15.0)
    assert reading_res.passed is True, f"Golden lesson failed reading level: {reading_res.reason}"

    # 2. Glossary coverage check
    glossary_res = check_glossary_coverage(lesson_text, glossary)
    assert glossary_res.passed is True, f"Golden lesson failed glossary coverage: {glossary_res.reason}"

    # 3. Required structure check
    structure_res = check_required_structure(lesson_text)
    assert structure_res.passed is True, f"Golden lesson failed structure: {structure_res.reason}"

    # 4. Quiz structure check (exactly 3 questions in Self-Check section)
    quiz_res = check_quiz_structure(lesson_text, required_count=3)
    assert quiz_res.passed is True, f"Golden lesson failed quiz: {quiz_res.reason}"
