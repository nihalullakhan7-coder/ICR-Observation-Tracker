"""
Minimal SQLite storage for observations extracted from uploaded photos.
No setup required -- creates icr.db as a plain file the first time it runs.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "icr.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            student_name TEXT,
            class TEXT,
            section TEXT,
            year TEXT,
            skill_code TEXT NOT NULL,
            level TEXT NOT NULL,
            date_recorded TEXT NOT NULL,
            match_status TEXT,
            extracted_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def insert_observations(student, match_status, skills):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    inserted = []

    for skill in skills:
        code = skill.get("skill_code")
        levels = skill.get("levels", {}) or {}
        for level, date_val in levels.items():
            if not date_val:
                continue
            conn.execute(
                """INSERT INTO observations
                   (student_id, student_name, class, section, year,
                    skill_code, level, date_recorded, match_status, extracted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (student or {}).get("student_id"),
                    (student or {}).get("name"),
                    (student or {}).get("class"),
                    (student or {}).get("section"),
                    (student or {}).get("year"),
                    code,
                    level,
                    date_val,
                    match_status,
                    now,
                ),
            )
            inserted.append({"skill_code": code, "level": level, "date_recorded": date_val})

    conn.commit()
    conn.close()
    return inserted


def get_all_observations(limit=200):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM observations ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
