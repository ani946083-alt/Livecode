import json
import os
import tempfile
import threading
from pathlib import Path


_DATA_DIRECTORY = Path(__file__).resolve().parent / "data"
_REPORTS_FILE = _DATA_DIRECTORY / "reports.json"
_FILE_LOCK = threading.Lock()
_REQUIRED_FIELDS = {
    "id",
    "area",
    "text",
    "depth_cm",
    "severity",
    "confidence",
    "needs_review",
    "created_at",
}


def _read_reports():
    _DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    if not _REPORTS_FILE.exists():
        _write_reports([])
        return []

    try:
        with _REPORTS_FILE.open("r", encoding="utf-8") as reports_file:
            reports = json.load(reports_file)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Stored reports contain invalid JSON: {_REPORTS_FILE}"
        ) from error

    if not isinstance(reports, list):
        raise RuntimeError("The reports JSON file must contain a list.")

    for index, report in enumerate(reports):
        if not isinstance(report, dict) or not _REQUIRED_FIELDS.issubset(report):
            raise RuntimeError(f"Stored report at position {index} is invalid.")

    return reports


def _write_reports(reports):
    _DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=_DATA_DIRECTORY,
            prefix="reports-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(reports, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, _REPORTS_FILE)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def get_all_reports():
    """Return all reports, creating an empty JSON file on first use."""
    with _FILE_LOCK:
        return _read_reports()


def add_report(report):
    """Append one report to JSON storage without discarding existing reports."""
    if not isinstance(report, dict):
        raise TypeError("A report must be a dictionary.")

    missing_fields = _REQUIRED_FIELDS.difference(report)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Report is missing required fields: {missing}")

    with _FILE_LOCK:
        reports = _read_reports()
        reports.append(report)
        _write_reports(reports)
