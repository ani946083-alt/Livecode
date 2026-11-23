"""
database.py  –  FloodWatch Storage Layer
==========================================
All interaction with reports.json is handled here.
No third-party database library is used – only Python's built-in json module.

Public API (used by app.py):
    load_reports()                        → list
    save_reports(reports)                 → None
    add_report(area, text, parsed)        → dict
    get_all_reports()                     → list
    mark_old_reports(reports)             → list
    get_active_reports(reports)           → list
    get_old_reports(reports)              → list
    get_conflict_reports(reports)         → list
    get_worst_flooded_areas(active)       → list
"""

import json
import os
import tempfile
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# File path – always next to this script, regardless of the working directory
# ---------------------------------------------------------------------------
REPORTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports.json")


# ---------------------------------------------------------------------------
# Private: safely create reports.json if it does not exist
# ---------------------------------------------------------------------------

def _ensure_file_exists():
    """
    Create reports.json with an empty array if it does not already exist.

    Uses exclusive-create mode ('x') so that two simultaneous first-calls
    cannot both try to create the file (race-condition safe).
    """
    try:
        # 'x' = create new file; raises FileExistsError if already present
        with open(REPORTS_FILE, "x", encoding="utf-8") as f:
            json.dump([], f)
    except FileExistsError:
        # File already exists – nothing to do
        pass


# ---------------------------------------------------------------------------
# Private: atomic file write
# ---------------------------------------------------------------------------

def _atomic_write(data):
    """
    Write JSON data to reports.json atomically.

    Writes to a temporary file in the same directory, then replaces the real
    file in one OS-level operation. This prevents a corrupt reports.json if
    the process crashes during a write.

    Args:
        data (list): The list of report dicts to persist.
    """
    dir_name = os.path.dirname(REPORTS_FILE)

    # NamedTemporaryFile in the same directory ensures os.replace() works
    # (cross-device moves are not atomic; same-directory moves always are).
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # indent=2 keeps the file human-readable – great for debugging
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Atomically replace the target file
        os.replace(tmp_path, REPORTS_FILE)
    except Exception:
        # Clean up the temp file if anything went wrong
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Core I/O – load and save
# ---------------------------------------------------------------------------

def load_reports():
    """
    Read all reports from reports.json and return them as a Python list.

    If the file does not exist, it is created automatically with [].
    If the file is empty or whitespace-only, return [].

    Returns:
        list: Every stored report dict.

    Raises:
        IOError:    If the file cannot be opened or read.
        ValueError: If the file contains non-JSON content.
    """
    _ensure_file_exists()

    try:
        # utf-8-sig transparently strips the BOM that tools like Windows
        # Notepad or PowerShell Out-File may prepend. Plain UTF-8 files are
        # also read correctly, so this codec is always safe.
        with open(REPORTS_FILE, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
    except IOError as e:
        raise IOError(f"Could not read reports.json: {e}") from e

    # Treat an empty file the same as an empty database
    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"reports.json contains invalid JSON: {e}") from e

    # Guard against a hand-edited file that is valid JSON but not a list
    if not isinstance(data, list):
        raise ValueError(
            "reports.json must contain a JSON array at the top level, "
            f"but found: {type(data).__name__}"
        )

    return data


def save_reports(reports):
    """
    Write the full list of reports back to reports.json (atomic write).

    Args:
        reports (list): The complete list of report dicts to persist.

    Raises:
        IOError: If the file cannot be written.
    """
    try:
        _atomic_write(reports)
    except IOError as e:
        raise IOError(f"Could not write reports.json: {e}") from e


# ---------------------------------------------------------------------------
# Private: auto-increment ID
# ---------------------------------------------------------------------------

def _next_id(reports):
    """
    Return the next integer ID for a new report.

    Finds the highest existing id and adds 1. Defaults to 1 when the
    database is empty. Uses .get("id", 0) so a hand-edited report that
    is missing its "id" key does not crash the server.

    Args:
        reports (list): The current list of stored report dicts.

    Returns:
        int: The next available ID.
    """
    if not reports:
        return 1
    return max(r.get("id", 0) for r in reports) + 1


# ---------------------------------------------------------------------------
# add_report – create, store, and return a new report
# ---------------------------------------------------------------------------

def add_report(area, text, parsed):
    """
    Build a new report object, persist it atomically, and return it.

    depth_cm is cast to int to keep the JSON file clean (the parser contract
    allows int or float; we always store int).

    Args:
        area   (str):  Flood area name (already stripped by the caller).
        text   (str):  Raw flood description (already stripped).
        parsed (dict): Validated result from parse_report(text).
                       Required keys: depth_cm, severity, confidence,
                       needs_review.

    Returns:
        dict: The complete report that was saved to disk.
    """
    reports = load_reports()

    # Capture time once so the stored value is consistent
    now_utc = datetime.now(timezone.utc)

    # Coerce depth_cm to int (parser may return float, e.g. 55.0)
    depth_cm = int(parsed["depth_cm"])

    # depth_cm must be non-negative
    if depth_cm < 0:
        depth_cm = 0

    report = {
        "id":           _next_id(reports),    # auto-increment integer
        "area":         area,                 # already stripped by caller
        "text":         text,                 # already stripped by caller
        "depth_cm":     depth_cm,
        "severity":     str(parsed["severity"]).strip(),
        "confidence":   float(parsed["confidence"]),
        "needs_review": bool(parsed["needs_review"]),
        # ISO-8601 with UTC offset – e.g. "2026-11-23T05:48:00+00:00"
        "created_at":   now_utc.isoformat(),
        # Always False on creation; mark_old_reports() updates this later
        "is_old":       False,
    }

    reports.append(report)
    save_reports(reports)

    return report


# ---------------------------------------------------------------------------
# get_all_reports – single call to get fresh data
# ---------------------------------------------------------------------------

def get_all_reports():
    """
    Load every report from disk with up-to-date is_old flags.

    Combining load + mark into one function means callers never need to
    remember to call mark_old_reports() separately.

    Returns:
        list: All reports with is_old recalculated from the current time.
    """
    reports = load_reports()
    reports = mark_old_reports(reports)
    return reports


# ---------------------------------------------------------------------------
# Private: datetime parser
# ---------------------------------------------------------------------------

def _parse_dt(report):
    """
    Convert the stored ISO-8601 string in report["created_at"] to a
    timezone-aware datetime object.

    Args:
        report (dict): A single report dict.

    Returns:
        datetime: Timezone-aware UTC datetime.

    Raises:
        ValueError: If "created_at" is missing or not a valid ISO-8601 string.
    """
    raw = report.get("created_at")
    if not raw:
        raise ValueError(
            f"Report id={report.get('id')} is missing the 'created_at' field."
        )
    return datetime.fromisoformat(raw)


# ---------------------------------------------------------------------------
# Old-report detection
# ---------------------------------------------------------------------------

def mark_old_reports(reports):
    """
    Set is_old = True on any report whose age exceeds 60 minutes.

    Mutates the list in-place and writes to disk only when at least one
    report changes state (avoids unnecessary disk writes on pure reads).

    Args:
        reports (list): The list returned by load_reports().

    Returns:
        list: The same list with is_old flags updated.
    """
    now_utc = datetime.now(timezone.utc)
    changed = False

    for report in reports:
        created = _parse_dt(report)
        age_minutes = (now_utc - created).total_seconds() / 60
        new_is_old = age_minutes > 60

        if report["is_old"] != new_is_old:
            report["is_old"] = new_is_old
            changed = True

    # Only hit the disk if something actually changed
    if changed:
        save_reports(reports)

    return reports


# ---------------------------------------------------------------------------
# Filtered views – pure functions, no disk I/O
# ---------------------------------------------------------------------------

def get_active_reports(reports):
    """
    Return only reports that are NOT old (is_old == False).

    Args:
        reports (list): Full list of report dicts.

    Returns:
        list: Reports created within the last 60 minutes.
    """
    return [r for r in reports if not r["is_old"]]


def get_old_reports(reports):
    """
    Return only reports that ARE old (is_old == True).

    Args:
        reports (list): Full list of report dicts.

    Returns:
        list: Reports older than 60 minutes.
    """
    return [r for r in reports if r["is_old"]]


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def get_conflict_reports(reports):
    """
    Return every report that is part of at least one conflict pair.

    A conflict exists when ALL three conditions are true for a pair:
      1. Same area name  (case-insensitive, whitespace-stripped)
      2. Created within 30 minutes of each other
      3. Water depth difference >= 20 cm

    Conflict detection runs over ALL reports (active and old alike),
    because an old report may still be conflicting with a recent one.

    Both reports in a conflicting pair are included in the result.
    Duplicate IDs are eliminated with a set.

    Args:
        reports (list): Full list of report dicts.

    Returns:
        list: Unique report dicts involved in at least one conflict,
              in their original order.
    """
    conflict_ids = set()

    # O(n²) pairwise comparison – perfectly fine for small datasets
    for i in range(len(reports)):
        for j in range(i + 1, len(reports)):
            r1 = reports[i]
            r2 = reports[j]

            # --- Condition 1: Same area (strip whitespace, ignore case) ---
            if r1["area"].strip().lower() != r2["area"].strip().lower():
                continue

            # --- Condition 2: Created within 30 minutes of each other ---
            t1 = _parse_dt(r1)
            t2 = _parse_dt(r2)
            diff_minutes = abs((t1 - t2).total_seconds()) / 60
            if diff_minutes > 30:
                continue

            # --- Condition 3: Depth difference >= 20 cm ---
            depth_diff = abs(r1["depth_cm"] - r2["depth_cm"])
            if depth_diff < 20:
                continue

            # All conditions met – mark both reports as conflicting
            conflict_ids.add(r1["id"])
            conflict_ids.add(r2["id"])

    # Preserve original list order
    return [r for r in reports if r["id"] in conflict_ids]


# ---------------------------------------------------------------------------
# Worst-flooded-area ranking
# ---------------------------------------------------------------------------

def get_worst_flooded_areas(active_reports):
    """
    Rank flood areas by their highest recorded depth (active reports only).

    For each unique area, the maximum depth_cm across all its active reports
    is used. Areas are returned sorted highest-first.

    Area names are compared case-insensitively and whitespace-stripped for
    deduplication, but the original casing of the highest-depth report is
    preserved in the output.

    Args:
        active_reports (list): Reports where is_old == False.

    Returns:
        list of dicts:
            [{"area": "School Road", "max_depth_cm": 90}, ...]
            sorted by max_depth_cm descending.
    """
    # key = lowercase-stripped area name
    # value = {"area": original_casing, "max_depth_cm": int}
    area_map = {}

    for report in active_reports:
        # Normalise the key so "School Road" and "school road" merge
        key = report["area"].strip().lower()
        depth = report["depth_cm"]

        if key not in area_map or depth > area_map[key]["max_depth_cm"]:
            area_map[key] = {
                "area":         report["area"],
                "max_depth_cm": depth,
            }

    # Highest depth first
    return sorted(
        area_map.values(),
        key=lambda x: x["max_depth_cm"],
        reverse=True,
    )
