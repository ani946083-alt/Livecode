# FloodWatch – Backend

> Real-Time Water Depth Monitoring System
> University Software Engineering Team Project – Backend Module

---

## Project Overview

FloodWatch collects crowd-sourced flood reports, parses depth information from
natural-language descriptions, and provides a live summary of which areas are
flooded, how severely, and whether any conflicting reports exist.

This module is the **backend only**: a REST API built with Python + Flask,
storing data in a single JSON file.

---

## Folder Structure

```
backend/
├── app.py            # Flask app – all API route handlers
├── database.py       # JSON read/write helpers + all business logic
├── reports.json      # Flat-file "database" (auto-created if missing)
├── requirements.txt  # Python package list
└── README.md         # This file
```

> **Not in this module:**
> `report_parser.py` is implemented by a teammate.
> See [Team Integration Notes](#team-integration-notes).

---

## Installation

### 1 · Clone the repository

```bash
git clone <your-repo-url>
cd backend
```

### 2 · Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

---

## How to Run

```bash
python app.py
```

The server starts at **http://127.0.0.1:5000** in debug mode.

> `debug=True` is set for development. It auto-reloads when you edit `.py`
> files and shows detailed tracebacks. Set it to `False` for any deployment.

> **Network note:** `host="0.0.0.0"` makes the server reachable on your local
> network (e.g. teammates can test it). Do not expose this to the internet
> without adding authentication and setting `debug=False`.

---

## API Documentation

### `POST /api/reports` – Submit a flood report

| Field  | Type   | Required | Max length | Description                        |
|--------|--------|----------|------------|------------------------------------|
| `area` | string | ✅        | 200 chars  | Name of the flooded location       |
| `text` | string | ✅        | 1000 chars | Natural-language flood description |

**Responses**

| Code | Meaning                              |
|------|--------------------------------------|
| 201  | Report saved – body contains report  |
| 400  | Missing / empty / oversized field, non-dict or invalid JSON body |
| 503  | `report_parser.py` not installed yet |
| 500  | Unexpected server error              |

---

### `GET /api/reports` – Get all reports

Returns every report stored in `reports.json`.
`is_old` flags are recalculated fresh on each request.
Returns `[]` when the database is empty.

| Code | Meaning          |
|------|------------------|
| 200  | Array of reports |
| 500  | File read error  |

---

### `GET /api/summary` – Get flood summary

| Code | Meaning          |
|------|------------------|
| 200  | Summary object   |
| 500  | Unexpected error |

**Summary fields**

| Field                 | Description                                                 |
|-----------------------|-------------------------------------------------------------|
| `total_reports`       | All reports ever submitted                                  |
| `active_reports`      | Reports created within the last 60 minutes                  |
| `old_reports`         | Reports older than 60 minutes                               |
| `conflict_reports`    | Number of reports involved in a conflict (see rules below)  |
| `worst_flooded_areas` | Active areas sorted by highest `depth_cm`, deepest first    |

> `active_reports + old_reports == total_reports` always.

---

## Business Rules

### Old Report Detection

```
age = current_time − created_at
is_old = True  when  age > 60 minutes
```

Old reports are excluded from `active_reports` and `worst_flooded_areas`.

### Conflict Detection

Two reports are **in conflict** when ALL three conditions are true:

1. **Same area** (case-insensitive, whitespace-stripped)
2. Created **within 30 minutes** of each other
3. `depth_cm` difference **≥ 20 cm**

Both reports in a conflicting pair appear in `conflict_reports`.
Conflict detection includes both active and old reports.

### Worst Flooded Areas

- Only active (non-old) reports are considered.
- For each area, the highest `depth_cm` is used.
- Sorted descending – the worst area appears first.

---

## Sample Requests and Responses

### Submit a report

**Git Bash / macOS / Linux:**
```bash
curl -X POST http://127.0.0.1:5000/api/reports \
     -H "Content-Type: application/json" \
     -d '{"area": "School Road", "text": "Water up to my knees"}'
```

**Windows PowerShell:**
```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:5000/api/reports `
  -ContentType "application/json" `
  -Body '{"area": "School Road", "text": "Water up to my knees"}'
```

**Expected response – 201 Created**
```json
{
  "id": 1,
  "area": "School Road",
  "text": "Water up to my knees",
  "depth_cm": 55,
  "severity": "High",
  "confidence": 0.92,
  "needs_review": false,
  "created_at": "2026-11-23T05:48:00+00:00",
  "is_old": false
}
```

---

### Get all reports

```bash
curl http://127.0.0.1:5000/api/reports
```

**Expected response – 200 OK**
```json
[
  {
    "id": 1,
    "area": "School Road",
    "text": "Water up to my knees",
    "depth_cm": 55,
    "severity": "High",
    "confidence": 0.92,
    "needs_review": false,
    "created_at": "2026-11-23T05:48:00+00:00",
    "is_old": false
  }
]
```

**When no reports exist – 200 OK**
```json
[]
```

---

### Get summary

```bash
curl http://127.0.0.1:5000/api/summary
```

**Expected response – 200 OK**
```json
{
  "total_reports": 3,
  "active_reports": 2,
  "old_reports": 1,
  "conflict_reports": 1,
  "worst_flooded_areas": [
    { "area": "School Road",   "max_depth_cm": 90 },
    { "area": "Market Street", "max_depth_cm": 55 }
  ]
}
```

---

### Error examples

**Missing field – 400**
```bash
curl -X POST http://127.0.0.1:5000/api/reports \
     -H "Content-Type: application/json" \
     -d '{"text": "Heavy flooding"}'
```
```json
{ "error": "Missing required field: 'area'." }
```

**Empty value – 400**
```bash
curl -X POST http://127.0.0.1:5000/api/reports \
     -H "Content-Type: application/json" \
     -d '{"area": "   ", "text": "Flood"}'
```
```json
{ "error": "Field 'area' must not be empty or whitespace." }
```

**Non-dict body – 400**
```bash
curl -X POST http://127.0.0.1:5000/api/reports \
     -H "Content-Type: application/json" \
     -d '[1, 2, 3]'
```
```json
{ "error": "Request body must be a JSON object ({\"area\": \"...\", \"text\": \"...\"})." }
```

**Parser not available – 503**
```json
{ "error": "Parser integration is not complete. Place report_parser.py ..." }
```

---

## Known Limitations

| Limitation | Detail |
|------------|--------|
| Parser dependency | `POST /api/reports` requires `report_parser.py` from a teammate |
| No authentication | No API keys or login – prototype only |
| No pagination | `GET /api/reports` always returns every report |
| Concurrency | JSON file storage is not safe for simultaneous writes (single-threaded dev server only) |
| File encoding | `reports.json` is read with `utf-8-sig` to handle BOM characters written by some Windows editors |

---

## Team Integration Notes

This backend works **alongside** `report_parser.py`, implemented by a different
team member.

**Contract – what parse_report() must return:**

```python
# report_parser.py must expose:
def parse_report(text: str) -> dict:
    ...
    return {
        "depth_cm":     55,       # int or float, must be >= 0
        "severity":     "High",   # non-empty string
        "confidence":   0.92,     # int or float (e.g. 0.0 – 1.0)
        "needs_review": False,    # bool (True or False)
    }
```

**To integrate:**
1. Your teammate finishes `report_parser.py`.
2. Place the file inside the `backend/` folder.
3. Restart the server: `python app.py`.
4. No other code changes are required.

Until the file is present, `POST /api/reports` returns `503 Service Unavailable`
with a clear explanation. `GET /api/reports` and `GET /api/summary` both work
without the parser.
