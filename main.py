"""
ICR core service -- flat layout (all files directly in backend/).

POST /extract          -- upload a photo, get structured observation data
                           back, AND it gets written to icr.db.
GET  /observations      -- JSON list of everything stored so far.
GET  /observations/view -- simple live HTML table (auto-refreshes).

Run locally, from the backend folder:
    uvicorn main:app --reload --port 8000
"""

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import db
from matcher import load_roster, match_student
from vision import extract_from_image

BASE_DIR = Path(__file__).parent
ROSTER_PATH = BASE_DIR / "students.csv"
SKILLS_PATH = BASE_DIR / "skills.json"

app = FastAPI(title="ICR core", version="0.2.0")

# Allow the frontend (running on a different port/origin, e.g. Live Server
# on :5501) to call this backend. For a class project/demo, allowing all
# origins is fine -- lock this down to specific origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False when allow_origins is "*" -- browsers
                              # reject the wildcard+credentials combo per spec
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


def _load_skill_codes():
    with open(SKILLS_PATH, encoding="utf-8") as f:
        skills = json.load(f)
    return [s["skill_code"] for s in skills]


class ExtractResponse(BaseModel):
    match_status: str
    student: dict | None
    match_confidence: float
    skills: list
    needs_review: list
    stored: list
    raw_extraction: dict


@app.post("/extract", response_model=ExtractResponse)
async def extract(photo: UploadFile = File(...)):
    if photo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Please upload a JPEG, PNG, or WEBP photo.")

    image_bytes = await photo.read()
    skill_codes = _load_skill_codes()

    try:
        extracted = extract_from_image(image_bytes, photo.content_type, skill_codes)
    except Exception as e:
        raise HTTPException(502, f"Vision extraction failed: {e}")

    student_fields = extracted.get("student", {}) or {}
    roster = load_roster(str(ROSTER_PATH))

    match = match_student(
        roster,
        ocr_name=student_fields.get("name") or "",
        ocr_class=student_fields.get("class") or "",
        ocr_section=student_fields.get("section") or "",
        ocr_year=student_fields.get("year") or "",
    )

    student_dict = (
        {
            "student_id": match.student.student_id,
            "name": match.student.name,
            "class": match.student.class_,
            "section": match.student.section,
            "year": match.student.year,
        }
        if match.student
        else None
    )

    skills = extracted.get("skills", [])
    stored = db.insert_observations(student_dict, match.status, skills)

    return ExtractResponse(
        match_status=match.status,
        student=student_dict,
        match_confidence=round(match.confidence, 2),
        skills=skills,
        needs_review=extracted.get("needs_review", []),
        stored=stored,
        raw_extraction=extracted,
    )


@app.get("/observations")
async def observations():
    return {"observations": db.get_all_observations()}


@app.get("/observations/view", response_class=HTMLResponse)
async def observations_view():
    rows = db.get_all_observations()
    row_html = "".join(
        f"""<tr>
              <td>{r['id']}</td>
              <td>{r['student_name'] or '-'}</td>
              <td>{r['class'] or '-'}</td>
              <td>{r['section'] or '-'}</td>
              <td>{r['skill_code']}</td>
              <td>{r['level']}</td>
              <td>{r['date_recorded']}</td>
              <td>{r['match_status']}</td>
              <td>{r['extracted_at']}</td>
            </tr>"""
        for r in rows
    )
    return f"""
    <html>
    <head>
      <title>ICR observations (live)</title>
      <meta http-equiv="refresh" content="5">
      <style>
        body {{ font-family: sans-serif; padding: 24px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; text-align: left; }}
        th {{ background: #f4f3ee; }}
      </style>
    </head>
    <body>
      <h2>Observations database (auto-refreshes every 5s)</h2>
      <p>{len(rows)} rows total. Upload a photo via /docs, then watch this page update.</p>
      <table>
        <tr><th>ID</th><th>Student</th><th>Class</th><th>Section</th>
            <th>Skill</th><th>Level</th><th>Date</th><th>Match</th><th>Stored at</th></tr>
        {row_html}
      </table>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok"}