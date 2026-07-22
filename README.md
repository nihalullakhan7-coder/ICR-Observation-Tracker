# ICR Observation Tracker

A FastAPI-based service that extracts handwritten student observation records from Observation Record sheets, matches them with the student database, and stores the extracted observations in a PostgreSQL database.

---

## Features

- 📷 Upload handwritten Observation Record images
- 🤖 AI-powered handwriting extraction using **Groq**
- 👨‍🎓 Automatic student matching
- 📊 Extracts observation dates for all skill levels (B / I / P / E)
- 💾 Stores extracted observations in PostgreSQL
- 🔍 Flags uncertain matches for manual review
- ⚡ FastAPI backend with Uvicorn

## Workflow

```
Observation Record Image
          │
          ▼
     AI Vision Extraction Groq
          │
          ▼
 Header & Skill Extraction
          │
          ▼
 Student Matching
          │
          ▼
 Structured JSON
          │
          ▼
 PostgreSQL Database
```

---

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- PostgreSQL
- psycopg2
- Pandas
- RapidFuzz
- Python-dotenv

---

## Project Structure

```
ProjectICR/
│
├── backend/
│   ├── main.py
│   ├── db.py
│   ├── matcher.py
│   ├── vision.py
│   ├── skills.json
│   ├── students.csv
│   ├── requirements.txt
│   ├── .env
│   └── README.md
│
├── frontend/
│   └── observation_tracker_front_end.html
│
└── sample_images/
```

---

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd ProjectICR/backend
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file inside the backend folder.

```env
DATABASE_URL=postgresql://username:password@host:5432/database_name
AI_API_KEY=your_api_key
```

---

## Running the Application

```bash
cd backend

uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

Backend URL:

```
http://localhost:8080
```

---

## API

### POST `/extract`

Uploads an Observation Record image and returns structured observation data.

#### Request

Multipart Form Data

```
photo=<image>
```

#### Response

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
  "match_confidence": 0.94,
  "skills": [
    {
      "skill_code": "S1",
      "levels": {
        "B": "12/05",
        "I": "14/06",
        "P": null,
        "E": null
      }
    }
  ],
  "needs_review": [],
  "raw_extraction": {}
}
```

---

## Student Matching

The matching process considers:

- Academic Year
- Class
- Section
- Fuzzy name matching

Possible results:

- `matched`
- `ambiguous`
- `not_found`

---

## Database

The Observation Tracker stores:

- Student Information
- Matched Student ID
- Observation Details
- Skill Progress
- Extraction Metadata
- Confidence Scores

The application connects to PostgreSQL using the `DATABASE_URL` specified in the `.env` file.

---

## Technologies

| Component | Technology |
|-----------|------------|
| Backend | FastAPI |
| API Server | Uvicorn |
| Database | PostgreSQL |
| Database Driver | psycopg2 |
| Data Processing | Pandas |
| Student Matching | RapidFuzz |
| Configuration | python-dotenv |

---

## Future Enhancements

- Bulk Image Upload
- PDF Support
- Admin Dashboard
- Analytics & Reports
- Authentication & Authorization

---

## License

Developed as part of the **ICR Observation Tracker** project.