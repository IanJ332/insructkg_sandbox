"""Draft Research Evaluation Instruments for Multi-Stakeholder Study (Phase 5.3).

Contains structured instruments for:
1. Student Perception Survey (Likert scale: cognitive load, AI helpfulness, EM relevance).
2. Instructor Pedagogical Review Rubric (correctness, pedagogical alignment, tone, actionability).
3. Blind Pairwise Evaluation Protocol (comparing Baseline vs RAG vs Verified KG).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


@dataclass
class SurveyQuestion:
    question_id: str
    category: str
    prompt: str
    scale_type: str  # e.g., 'likert_5', 'free_text'
    min_label: str
    max_label: str


STUDENT_PERCEPTION_SURVEY: List[SurveyQuestion] = [
    SurveyQuestion(
        question_id="SPS_01",
        category="Cognitive Load",
        prompt="The AI-generated feedback clearly highlighted where my query diverged without overwhelming me with excessive text.",
        scale_type="likert_5",
        min_label="Strongly Disagree",
        max_label="Strongly Agree",
    ),
    SurveyQuestion(
        question_id="SPS_02",
        category="Pedagogical Actionability",
        prompt="The guidance provided clear, actionable next steps rather than simply revealing the exact SQL solution.",
        scale_type="likert_5",
        min_label="Strongly Disagree",
        max_label="Strongly Agree",
    ),
    SurveyQuestion(
        question_id="SPS_03",
        category="Curriculum Grounding",
        prompt="The lecture citations and concept references matched what was covered in our course materials.",
        scale_type="likert_5",
        min_label="Strongly Disagree",
        max_label="Strongly Agree",
    ),
    SurveyQuestion(
        question_id="SPS_04",
        category="Entrepreneurial Mindset (EM)",
        prompt="The optional reflection prompt helped me understand how this SQL query connects to real-world organizational decisions and downstream systems.",
        scale_type="likert_5",
        min_label="Strongly Disagree",
        max_label="Strongly Agree",
    ),
    SurveyQuestion(
        question_id="SPS_05",
        category="Open-Ended Synthesis",
        prompt="The personalized dynamic project aligned with my professional interests and deepened my understanding of multi-table database design.",
        scale_type="likert_5",
        min_label="Strongly Disagree",
        max_label="Strongly Agree",
    ),
]


@dataclass
class RubricCriterion:
    criterion_id: str
    name: str
    description: str
    weight: float
    scoring_levels: Dict[int, str]


INSTRUCTOR_REVIEW_RUBRIC: List[RubricCriterion] = [
    RubricCriterion(
        criterion_id="IRR_01",
        name="Technical & Relational Correctness",
        description="Is the technical SQL explanation and relational algebra rationale factually accurate?",
        weight=0.30,
        scoring_levels={
            1: "Contains critical relational misconceptions (e.g. confusing WHERE with ON).",
            2: "Partially correct but misleading on edge cases (e.g. NULL comparisons).",
            3: "Technically sound and accurately distinguishes join semantics.",
        },
    ),
    RubricCriterion(
        criterion_id="IRR_02",
        name="Solution Concealment (Pedagogical Tone)",
        description="Does the feedback guide the learner toward self-correction without leaking the solution SQL?",
        weight=0.25,
        scoring_levels={
            1: "Directly reveals the reference SQL query or clause verbatim.",
            2: "Provides overly narrow hints that require little independent thinking.",
            3: "Successfully diagnoses the gap while withholding the direct code solution.",
        },
    ),
    RubricCriterion(
        criterion_id="IRR_03",
        name="InstructKG & Lecture Alignment",
        description="Are cited concepts and course materials authentic and appropriately contextualized?",
        weight=0.25,
        scoring_levels={
            1: "Hallucinates non-existent lecture sections or irrelevant concepts.",
            2: "Cites general database concepts without curriculum alignment.",
            3: "Accurately references verified course lectures and prerequisite concepts.",
        },
    ),
    RubricCriterion(
        criterion_id="IRR_04",
        name="Entrepreneurial Mindset Relevance",
        description="Does the EM reflection prompt encourage genuine inquiry (C), cross-system connections (X), or stakeholder value (V)?",
        weight=0.20,
        scoring_levels={
            1: "Superficial or disconnected from database design reality.",
            2: "Relevant business scenario but lacks connection to query semantics.",
            3: "Compelling authentic connection between relational semantics and organizational impact.",
        },
    ),
]


BLIND_REVIEW_PROTOCOL: Dict[str, Any] = {
    "protocol_name": "Blinded Multi-Condition SQL Guidance Review",
    "version": "1.0.0",
    "blinding_procedure": (
        "Conditions (Baseline, RAG, KG-Grounding) are assigned randomized anonymized identifiers "
        "(Option Alpha, Option Beta, Option Gamma). System prompts, evidence digests, and model metadata "
        "are completely redacted from the reviewer evaluation packet."
    ),
    "evaluation_tasks": [
        "Select preferred feedback candidate (Rank 1, 2, 3).",
        "Rate technical accuracy on 5-point scale.",
        "Rate pedagogical helpfulness on 5-point scale.",
        "Identify any perceived hallucination or solution disclosure.",
    ],
}


def get_evaluation_instruments() -> Dict[str, Any]:
    return {
        "student_perception_survey": [asdict(q) for q in STUDENT_PERCEPTION_SURVEY],
        "instructor_review_rubric": [asdict(r) for r in INSTRUCTOR_REVIEW_RUBRIC],
        "blind_review_protocol": BLIND_REVIEW_PROTOCOL,
    }
