"""Pydantic schemas and state definitions for the Lesson Agent system."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class LearnerProfile(BaseModel):
    """Target learner demographic and background profile."""

    target_group: str = "12th-grade graduate from India"
    schooling_medium: str = "Non-English-medium background"
    english_proficiency: str = "Limited English vocabulary, needs simple words and short sentences"
    technical_background: str = "Zero technical background, complete beginner"
    aspiration: str = "Wants to start an AI career"


class WhatWhyHow(BaseModel):
    """Core breakdown of what RAG is, why it matters, and how it works."""

    what: str = Field(description="What RAG is in simple words")
    why: str = Field(description="Why RAG matters and why standard LLMs fall short")
    how: str = Field(description="How the RAG pipeline operates step by step")


class LessonPlan(BaseModel):
    """Structured outline produced by the Planner node."""

    topic: str
    what_why_how: WhatWhyHow
    key_concepts: List[str] = Field(
        description="The 8 mandatory concepts: retrieval, embeddings, vector database, chunking, augmenting the prompt, generation, hallucination reduction, limitations"
    )
    outline: List[str] = Field(
        description="Sequential section-by-section outline of the lesson"
    )


class FactItem(BaseModel):
    """Ground truth factual entry verified against research papers and official docs."""

    id: str
    fact: str
    source_name: str
    source_url: str
    category: str


class CheckResult(BaseModel):
    """Result of an individual rubric check."""

    check_id: str
    passed: bool
    reason: str
    evidence_quote: str = Field(
        default="",
        description="Verbatim excerpt from the draft demonstrating the violation. Can be empty if a required element is entirely missing.",
    )


class EvaluationResult(BaseModel):
    """Aggregate result of all hybrid deterministic and LLM checks."""

    passed: bool
    checks: List[CheckResult]
    failing_checks: List[str] = Field(default_factory=list)

    @property
    def fail_count(self) -> int:
        return len(self.failing_checks)

    @property
    def pass_count(self) -> int:
        return len(self.checks) - len(self.failing_checks)


class LessonAttempt(BaseModel):
    """A single generation or revision attempt of the lesson."""

    attempt_number: int
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    evaluation: Optional[EvaluationResult] = None
    changes_made: Optional[str] = None
    fault_injected: Optional[str] = None


class LearnedRule(BaseModel):
    """A self-evolved heuristic extracted from recurring rejection patterns."""

    id: Optional[int] = None
    rule_text: str
    source_check_id: str
    failure_count: int = 1
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class LessonState(BaseModel):
    """LangGraph state representation passed through all pipeline nodes."""

    topic: str = "Introduction to RAG (Retrieval-Augmented Generation)"
    learner_profile: LearnerProfile = Field(default_factory=LearnerProfile)
    plan: Optional[LessonPlan] = None
    fact_pack: List[FactItem] = Field(default_factory=list)
    glossary: Dict[str, str] = Field(default_factory=dict)  # Amendment 4: default must be {}
    learned_rules: List[str] = Field(default_factory=list)
    attempts: List[LessonAttempt] = Field(default_factory=list)
    current_attempt: int = 0
    max_retries: int = 2
    status: Literal[
        "generating",
        "evaluating",
        "passed",
        "revising",
        "needs_human_review",
        "completed",
    ] = "generating"
    final_lesson: Optional[str] = None
    fault_to_inject: Optional[str] = None
    run_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def get_best_attempt(self) -> Optional[LessonAttempt]:
        """Amendment 10: 'Best attempt' = fewest failing checks."""
        if not self.attempts:
            return None
        valid_attempts = [a for a in self.attempts if a.evaluation is not None]
        if not valid_attempts:
            return self.attempts[-1]
        return min(valid_attempts, key=lambda a: a.evaluation.fail_count)

