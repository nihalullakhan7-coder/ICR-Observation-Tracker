"""
Matches the (often imperfectly OCR'd) student header fields read off a
photographed Observation Record page against a known student roster.

Matching strategy:
  1. Narrow the roster to exact matches on class + section + year first —
     this is a small, low-ambiguity search space.
  2. Within that narrowed set, fuzzy-match the handwritten/OCR'd name.
  3. If exactly one strong match is found, return it with high confidence.
  4. If zero or multiple plausible matches are found, return no match and
     flag it for manual confirmation instead of guessing.
"""

import csv
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Student:
    student_id: str
    name: str
    class_: str
    section: str
    year: str


@dataclass
class MatchResult:
    status: str  # "matched" | "ambiguous" | "not_found"
    student: Optional[Student]
    confidence: float
    candidates: list[Student]


def load_roster(csv_path: str) -> list[Student]:
    students = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            students.append(
                Student(
                    student_id=row["student_id"],
                    name=row["name"],
                    class_=row["class"],
                    section=row["section"],
                    year=row["year"],
                )
            )
    return students


def _normalize(s: str) -> str:
    return " ".join(s.strip().lower().split())


def match_student(
    roster: list[Student],
    ocr_name: str,
    ocr_class: str,
    ocr_section: str,
    ocr_year: str,
    name_threshold: float = 0.6,
) -> MatchResult:
    # Step 1: narrow by class + section + year (exact, case-insensitive)
    narrowed = [
        s
        for s in roster
        if _normalize(s.class_) == _normalize(ocr_class)
        and _normalize(s.section) == _normalize(ocr_section)
        and _normalize(s.year) == _normalize(ocr_year)
    ]

    if not narrowed:
        return MatchResult(status="not_found", student=None, confidence=0.0, candidates=[])

    # Step 2: fuzzy-match the name within the narrowed set
    scored = []
    for s in narrowed:
        ratio = difflib.SequenceMatcher(
            None, _normalize(s.name), _normalize(ocr_name)
        ).ratio()
        scored.append((ratio, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_ratio, best_student = scored[0]

    if best_ratio < name_threshold:
        return MatchResult(
            status="not_found",
            student=None,
            confidence=best_ratio,
            candidates=[s for _, s in scored[:5]],
        )

    # Check if there's a close second candidate (ambiguous)
    if len(scored) > 1:
        second_ratio = scored[1][0]
        if best_ratio - second_ratio < 0.1:
            return MatchResult(
                status="ambiguous",
                student=None,
                confidence=best_ratio,
                candidates=[s for _, s in scored[:5]],
            )

    return MatchResult(
        status="matched",
        student=best_student,
        confidence=best_ratio,
        candidates=[best_student],
    )
