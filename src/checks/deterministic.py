"""Deterministic code-based checks for lesson evaluation.

Covers:
- Markdown stripping
- Reading level (Flesch-Kincaid Grade Level <= 7.0 & Avg Sentence Length <= 15.0 words)
- Glossary coverage (terms defined at first use)
- Required document structure (headings, worked example, summary)
- Quiz structure (exactly 3 numbered self-check questions in the Self-Check section)
"""

import re
from typing import Dict, List, Optional, Tuple
import textstat

from src.schemas import CheckResult


def strip_markdown(text: str) -> str:
    """Strip markdown formatting syntax to produce clean natural language prose.

    Amendment 3: Strip headings, bullets, code fences, inline code, bold, italics,
    and links before computing Flesch-Kincaid and sentence length.
    """
    if not text:
        return ""

    # Remove code blocks (```...```)
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code (`...`)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    # Remove images (![alt](url))
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    # Replace links [text](url) with text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cleaned)
    # Punctuate headings before stripping marks so they aren't merged with subsequent prose
    def _punctuate_heading(m):
        h = m.group(1).strip()
        if h and h[-1] not in ".!?:":
            return h + "."
        return h

    cleaned = re.sub(r"^\s*#{1,6}\s+(.+)$", _punctuate_heading, cleaned, flags=re.MULTILINE)
    # Remove bullet markers (*, -, +)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    # Remove numbered list prefixes (1. , 2. )
    cleaned = re.sub(r"^\s*\d+[\.\)]\s+", "", cleaned, flags=re.MULTILINE)
    # Remove bold and italic markers (**text**, *text*, __text__, _text_)
    cleaned = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", cleaned)
    # Remove blockquotes (> quote)
    cleaned = re.sub(r"^\s*>\s*", "", cleaned, flags=re.MULTILINE)
    # Remove horizontal rules (--- or ***)
    cleaned = re.sub(r"^\s*[-*_]{3,}\s*$", " ", cleaned, flags=re.MULTILINE)
    # Normalize multiple whitespace and newlines
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)

    return cleaned.strip()


def calculate_sentence_metrics(text: str) -> Tuple[float, int, int]:
    """Calculate average sentence length, total words, and total sentences.

    Returns:
        (avg_sentence_length, total_words, total_sentences)
    """
    clean_text = strip_markdown(text)
    if not clean_text:
        return 0.0, 0, 0

    # Split into sentences using terminal punctuation or line breaks
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", clean_text)
    # Filter out empty or whitespace-only sentences
    sentences = [s.strip() for s in raw_sentences if re.search(r"\w+", s)]

    if not sentences:
        return 0.0, 0, 0

    total_words = 0
    for s in sentences:
        words = re.findall(r"\b[A-Za-z0-9'-]+\b", s)
        total_words += len(words)

    total_sentences = len(sentences)
    avg_sentence_len = total_words / total_sentences if total_sentences > 0 else 0.0

    return avg_sentence_len, total_words, total_sentences


def check_reading_level(
    text: str,
    max_grade: float = 7.0,
    max_avg_sentence_len: float = 15.0,
    glossary: Optional[Dict[str, str]] = None,
) -> CheckResult:
    """Verify readability criteria: FK grade <= 7.0 AND avg sentence length <= 15.0 words.

    Calculated strictly on prose with markdown syntax stripped.
    Provides actionable diagnostic feedback including exact sentences over 15 words
    and multi-syllable non-glossary words to simplify.
    """
    clean_text = strip_markdown(text)
    if not clean_text or len(clean_text.split()) < 20:
        return CheckResult(
            check_id="reading_level",
            passed=False,
            reason="Lesson draft is too short to evaluate readability accurately.",
            evidence_quote="",
        )

    # Compute Flesch-Kincaid Grade Level
    fk_grade = textstat.flesch_kincaid_grade(clean_text)
    avg_sentence_len, total_words, total_sentences = calculate_sentence_metrics(text)

    # Extract sentences
    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", clean_text)
        if re.search(r"\w+", s)
    ]

    # Identify all sentences over 15 words
    long_sentences: List[Tuple[int, str]] = []
    for s in raw_sentences:
        words = re.findall(r"\b[A-Za-z0-9'-]+\b", s)
        if len(words) > 15:
            long_sentences.append((len(words), s))
    long_sentences.sort(key=lambda x: x[0], reverse=True)

    # Extract multi-syllable non-glossary words (>= 3 syllables)
    glossary_tokens = set()
    if glossary:
        for k in glossary.keys():
            glossary_tokens.update(k.lower().split())
    else:
        glossary_tokens = {
            "rag", "retrieval", "augmented", "generation", "embeddings", "embedding",
            "vector", "database", "chunking", "chunks", "prompt", "prompts",
            "hallucination", "hallucinations", "limitations", "grounding",
            "parametric", "non-parametric", "external", "knowledge", "artificial",
            "intelligence"
        }

    all_words = re.findall(r"\b[A-Za-z]{3,}\b", clean_text)
    hard_words = []
    seen_hard = set()
    for w in all_words:
        low = w.lower()
        if low not in glossary_tokens and low not in seen_hard:
            if textstat.syllable_count(w) >= 3:
                seen_hard.add(low)
                hard_words.append(low)

    grade_pass = fk_grade <= max_grade
    sentence_len_pass = avg_sentence_len <= max_avg_sentence_len
    all_pass = grade_pass and sentence_len_pass

    # Pick evidence quote: longest violating sentence that exists verbatim in original text
    evidence_quote = ""
    for _, s in long_sentences:
        if s in text:
            evidence_quote = s
            break
    if not evidence_quote and long_sentences:
        # Search unstripped lines for match
        first_few = " ".join(long_sentences[0][1].split()[:5])
        for line in text.splitlines():
            if first_few in line:
                evidence_quote = line.strip()
                break

    if all_pass:
        reason = (
            f"FK Grade: {fk_grade:.2f} (target <= {max_grade}), "
            f"Avg Sentence Length: {avg_sentence_len:.2f} words (target <= {max_avg_sentence_len})."
        )
    else:
        reasons = []
        if not grade_pass:
            reasons.append(
                f"Reading level grade ({fk_grade:.2f}) is too difficult for target beginner learner "
                f"(exceeds target <= {max_grade}, failing by {fk_grade - max_grade:+.2f})."
            )
        if not sentence_len_pass:
            reasons.append(
                f"Average sentence length ({avg_sentence_len:.2f} words) exceeds maximum allowable {max_avg_sentence_len} words "
                f"(failing by {avg_sentence_len - max_avg_sentence_len:+.2f} words)."
            )

        if long_sentences:
            sample_long = [f'"{s}" ({count} words)' for count, s in long_sentences[:5]]
            reasons.append(
                f"Exact sentences over 15 words to split ({len(long_sentences)} total):\n  - "
                + "\n  - ".join(sample_long)
            )

        if hard_words:
            reasons.append(
                f"Multi-syllable non-glossary words to simplify: {', '.join(hard_words[:12])}."
            )

        reason = "\n".join(reasons)

    return CheckResult(
        check_id="reading_level",
        passed=all_pass,
        reason=reason.strip(),
        evidence_quote=evidence_quote,
    )


# Common patterns that signal a definitional statement
DEFINITION_INDICATORS = [
    r"\bis\b",
    r"\bare\b",
    r"\bmeans\b",
    r"\brefers to\b",
    r"\bstands for\b",
    r"\bshort for\b",
    r"\bdefined as\b",
    r"\bthink of (?:it|this) as\b",
    r"\bin simple words\b",
    r"\bwhich is\b",
    r"\bknown as\b",
    r"\bcall(?:ed|s)?\b",
    r":",
    r"—",
    r"\(.*?\)",
]


def check_glossary_coverage(text: str, glossary: Dict[str, str]) -> CheckResult:
    """Verify that every technical term from glossary that appears is defined at first use.

    Amendment 8: Glossary has max 12 terms.
    Checks that the sentence containing the first occurrence of each term in prose,
    or the immediately adjacent sentence (preceding or succeeding), defines the term
    in simple language before it is used freely in the lesson. Headings (# and ##)
    are excluded so that section titles are not falsely treated as body definitions.
    """
    if not glossary:
        return CheckResult(
            check_id="jargon_defined",
            passed=True,
            reason="Glossary is empty; check bypassed.",
            evidence_quote="",
        )

    # Exclude markdown headers from prose definition checks
    prose_text = re.sub(r"^\s*#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    clean_text = strip_markdown(prose_text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_text) if s.strip()]

    undefined_terms: List[Tuple[str, str]] = []

    for term in glossary.keys():
        # Match standalone term with word boundaries
        term_pattern = r"\b" + re.escape(term) + r"\b"

        first_idx = None
        for idx, s in enumerate(sentences):
            if re.search(term_pattern, s, flags=re.IGNORECASE):
                first_idx = idx
                break

        if first_idx is not None:
            first_sentence = sentences[first_idx]
            has_definition_first = any(
                re.search(ind, first_sentence, flags=re.IGNORECASE)
                for ind in DEFINITION_INDICATORS
            )

            # Check immediate next sentence (first_idx + 1)
            has_definition_next = False
            if first_idx + 1 < len(sentences):
                next_sentence = sentences[first_idx + 1]
                has_definition_next = any(
                    re.search(ind, next_sentence, flags=re.IGNORECASE)
                    for ind in DEFINITION_INDICATORS
                )

            # Check immediate preceding sentence (first_idx - 1)
            has_definition_prev = False
            if first_idx > 0:
                prev_sentence = sentences[first_idx - 1]
                has_definition_prev = any(
                    re.search(ind, prev_sentence, flags=re.IGNORECASE)
                    for ind in DEFINITION_INDICATORS
                )

            if not (has_definition_first or has_definition_next or has_definition_prev):
                undefined_terms.append((term, first_sentence))

    if undefined_terms:
        failing_term, violating_sentence = undefined_terms[0]
        # Find corresponding original sentence in uncleaned text for verbatim quote
        quote = violating_sentence if violating_sentence in text else ""
        return CheckResult(
            check_id="jargon_defined",
            passed=False,
            reason=f"Technical term '{failing_term}' is introduced without an immediate simple definition at first use.",
            evidence_quote=quote,
        )

    return CheckResult(
        check_id="jargon_defined",
        passed=True,
        reason="All technical terms from the glossary that appear in the lesson are properly defined at first use.",
        evidence_quote="",
    )


def check_required_structure(text: str) -> CheckResult:
    """Verify presence of essential structural elements: title, headings, worked example, and summary."""
    has_title = bool(re.search(r"^\s*#\s+.+", text, flags=re.MULTILINE))
    has_headings = len(re.findall(r"^\s*##\s+.+", text, flags=re.MULTILINE)) >= 3
    has_example = bool(
        re.search(
            r"(?i)(?:worked example|real-world example|step-by-step example|example in action)",
            text,
        )
    )
    has_summary = bool(
        re.search(
            r"(?i)##+\s*(?:\d+[\.\)]\s*)?(?:key takeaway|summary|wrap-up|quick review|lesson summary)",
            text,
        )
    )

    missing = []
    if not has_title:
        missing.append("Main Title (#)")
    if not has_headings:
        missing.append("At least 3 major sections (##)")
    if not has_example:
        missing.append("Worked Example section")
    if not has_summary:
        missing.append("Summary section")

    passed = len(missing) == 0
    reason = (
        "Lesson satisfies required structural sections."
        if passed
        else f"Missing required structural sections: {', '.join(missing)}."
    )

    return CheckResult(
        check_id="required_structure",
        passed=passed,
        reason=reason,
        evidence_quote="",
    )


def check_quiz_structure(text: str, required_count: int = 3) -> CheckResult:
    """Verify that lesson ends with a summary and exactly 3 numbered self-check questions.

    Amendment 2: Quiz check counts numbered items ONLY within the 'Self-Check' section.
    """
    # Look for Self-Check section header
    pattern = r"(?i)(?:##+\s*(?:\d+[\.\)]\s*)?(?:self[- ]check|quiz|test your knowledge|check your understanding|quick quiz)[^\n]*)([\s\S]*)"
    match = re.search(pattern, text)

    if not match:
        return CheckResult(
            check_id="wrap_up",
            passed=False,
            reason="Missing 'Self-Check' section at the end of the lesson.",
            evidence_quote="",
        )

    quiz_section_text = match.group(1)

    # If another subsequent H2 header exists, trim quiz section text to that boundary
    subsequent_header = re.search(r"\n##+\s+", quiz_section_text)
    if subsequent_header:
        quiz_section_text = quiz_section_text[: subsequent_header.start()]

    # Count numbered list items (e.g., "1. Question", "2) Question")
    numbered_items = re.findall(
        r"^\s*\d+[\.\)]\s+.+", quiz_section_text, flags=re.MULTILINE
    )
    count = len(numbered_items)

    passed = count == required_count
    if passed:
        reason = f"Contains exactly {required_count} numbered self-check questions in the Self-Check section."
    else:
        reason = (
            f"Expected exactly {required_count} numbered self-check questions in the Self-Check section, "
            f"but found {count}."
        )

    return CheckResult(
        check_id="wrap_up",
        passed=passed,
        reason=reason,
        evidence_quote=numbered_items[0] if numbered_items and not passed else "",
    )
