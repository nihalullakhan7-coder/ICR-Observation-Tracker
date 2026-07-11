# ICR core

A standalone service: **photo of a filled Observation Record page in →
structured, student-matched JSON out.** No user accounts, no app
integration — just the extraction core.

## What it does

1. You POST a photo to `/extract`.
2. It sends the photo to Claude (vision) with instructions to read the
   handwritten header (name/class/section/year) and, for every skill row,
   check whether each level (B/I/P/E) has an actual handwritten date in
   its date box.
   - **A level is only ever marked if a date is literally present.**
     No auto-filling lower levels from a higher one, no guessing on
     illegible handwriting — those come back `null` and land in
     `needs_review`.
3. It matches the handwritten student header against your own roster
   (`data/students.csv`), narrowing by class + section + year first,
   then fuzzy-matching the name.
4. It returns one JSON object with everything: the matched student (or
   `not_found` / `ambiguous` if it couldn't confidently match), which
   skill levels were dated, and the raw extraction for debugging.

## Setup
```bash
cd icr-core
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

## Usage

```bash
curl -X POST http://localhost:8000/extract \
  -F "photo=@sample_record.jpg"
```

Example response:

```json
{
  "match_status": "matched",
  "student": {
    "student_id": "STU001",
    "name": "Anika K.",
    "class": "UKG",
    "section": "Section A",
    "year": "2026"
  },
  "match_confidence": 0.93,
  "skills": [
    {"skill_code": "S1", "levels": {"B": "12/05", "I": "14/06", "P": null, "E": null}},
    {"skill_code": "S2", "levels": {"B": null, "I": null, "P": null, "E": null}}
  ],
  "needs_review": [],
  "raw_extraction": { "...": "full model output, kept for debugging" }
}
```

## Files

```
icr-core/
  app/
    main.py      FastAPI app, the /extract endpoint
    vision.py     Calls Claude with the photo, returns structured JSON
    matcher.py    Matches OCR'd student fields against your roster
  data/
    students.csv  Your student roster (name, class, section, year) — edit this
    skills.json   Skill definitions currently covering S1-S6 (Month 1)
  requirements.txt
```

## Extending

- **More skills**: add entries to `data/skills.json` in the same shape.
  The `skill_codes` list passed to the vision prompt is read straight
  from this file, so no code changes needed — just data.
- **Bigger/different roster**: edit `data/students.csv` directly, or
  swap `load_roster()` in `matcher.py` for a real database call if the
  list grows past what's comfortable in a spreadsheet.
- **`match_status` handling**: your caller should treat `"ambiguous"`
  and `"not_found"` as "needs a human to pick the right student" rather
  than silently dropping the observation or guessing.
- **Model choice**: `vision.py` uses a strong vision model for
  handwriting since accuracy matters here; swap `MODEL` if you want to
  trade cost for speed once you've validated accuracy on real photos.

## Not included (by design, per current scope)

No auth, no database, no UI, no student-management screens — this is
just the extraction core. It returns JSON; what you do with it
(write to a database, show it in a review screen, etc.) is up to
whatever calls this service.
