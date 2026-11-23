import math
import uuid
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from database import add_report, get_all_reports

try:
    from report_parser import parse_report
except ModuleNotFoundError as error:
    if error.name != "report_parser":
        raise
    parse_report = None


app = Flask(__name__)
OLD_REPORT_AFTER = timedelta(minutes=60)
CONFLICT_WINDOW = timedelta(minutes=30)
CONFLICT_DEPTH_DIFFERENCE_CM = 20
MAX_WORST_AREAS = 5


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


def _now():
    return datetime.now(timezone.utc)


def _parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Report created_at must be an ISO-8601 string.")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Report created_at is not a valid ISO-8601 timestamp.") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _report_is_old(report, now):
    return now - _parse_timestamp(report["created_at"]) > OLD_REPORT_AFTER


def _valid_depth(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _report_depth(report):
    depth = report.get("depth_cm")
    return depth if _valid_depth(depth) else None


def _find_conflicts(reports):
    conflicts = []

    for first_index, first in enumerate(reports):
        first_area = first["area"].strip().casefold()
        first_depth = _report_depth(first)
        if not first_area or first_depth is None:
            continue

        first_time = _parse_timestamp(first["created_at"])

        for second in reports[first_index + 1:]:
            if second["area"].strip().casefold() != first_area:
                continue

            second_depth = _report_depth(second)
            if second_depth is None:
                continue

            second_time = _parse_timestamp(second["created_at"])
            time_difference = abs(first_time - second_time)
            depth_difference = abs(first_depth - second_depth)

            if (
                time_difference <= CONFLICT_WINDOW
                and depth_difference >= CONFLICT_DEPTH_DIFFERENCE_CM
            ):
                conflicts.append({
                    "area": first["area"],
                    "report_ids": [first["id"], second["id"]],
                    "depths_cm": [first_depth, second_depth],
                    "difference_cm": depth_difference,
                    "reported_at": [first["created_at"], second["created_at"]],
                })

    return conflicts


def _public_reports(reports, now, conflicts):
    conflicting_ids = {
        report_id
        for conflict in conflicts
        for report_id in conflict["report_ids"]
    }

    return [
        {
            "id": report["id"],
            "area": report["area"],
            "text": report["text"],
            "depth_cm": report["depth_cm"],
            "severity": report["severity"],
            "confidence": report["confidence"],
            "needs_review": report["needs_review"],
            "created_at": report["created_at"],
            "is_old": _report_is_old(report, now),
            "has_conflict": report["id"] in conflicting_ids,
        }
        for report in reports
    ]


def _severity_rank(severity):
    normalized = str(severity).strip().casefold()

    if any(word in normalized for word in ("critical", "extreme", "severe")):
        return 4
    if any(word in normalized for word in ("high", "danger")):
        return 3
    if any(word in normalized for word in ("moderate", "medium")):
        return 2
    if any(word in normalized for word in ("low", "mild")):
        return 1
    return 0


def _area_summaries(reports, now, conflicts):
    recent_by_area = {}
    conflict_areas = {
        conflict["area"].strip().casefold()
        for conflict in conflicts
    }

    for report in reports:
        if _report_is_old(report, now):
            continue
        key = report["area"].strip().casefold()
        if key:
            recent_by_area.setdefault(key, []).append(report)

    summaries = []
    for area_reports in recent_by_area.values():
        latest = max(area_reports, key=lambda report: _parse_timestamp(report["created_at"]))
        depths = [
            depth for depth in (_report_depth(report) for report in area_reports)
            if depth is not None
        ]
        summaries.append({
            "area": latest["area"],
            "status": latest["severity"],
            "depth_cm": latest["depth_cm"],
            "max_depth_cm": max(depths) if depths else None,
            "confidence": latest["confidence"],
            "needs_review": any(report["needs_review"] for report in area_reports),
            "report_count": len(area_reports),
            "latest_report_at": latest["created_at"],
            "latest_text": latest["text"],
            "has_conflict": latest["area"].strip().casefold() in conflict_areas,
        })

    summaries.sort(
        key=lambda area: (
            -_severity_rank(area["status"]),
            -(area["max_depth_cm"] if area["max_depth_cm"] is not None else -1),
            -_parse_timestamp(area["latest_report_at"]).timestamp(),
        )
    )
    return summaries


def _load_reports_or_error():
    try:
        return get_all_reports(), None
    except (OSError, RuntimeError) as error:
        app.logger.exception("Could not read report storage.")
        return None, (jsonify({"error": str(error)}), 500)


@app.post("/api/reports")
def create_report():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json."}), 415

    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    area = payload.get("area")
    text = payload.get("text")
    if not isinstance(area, str) or not area.strip():
        return jsonify({"error": "area must be a non-empty string."}), 400
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text must be a non-empty string."}), 400
    if len(area.strip()) > 200:
        return jsonify({"error": "area must be 200 characters or fewer."}), 400
    if len(text.strip()) > 2000:
        return jsonify({"error": "text must be 2000 characters or fewer."}), 400
    if parse_report is None:
        return jsonify({
            "error": (
                "Report parser is unavailable. Add report_parser.py with "
                "parse_report(text) before submitting reports."
            )
        }), 503

    try:
        parsed = parse_report(text.strip())
    except (TypeError, ValueError):
        app.logger.exception("The report parser failed.")
        return jsonify({"error": "The report parser failed to process this report."}), 500

    if not isinstance(parsed, dict):
        app.logger.error("parse_report(text) did not return a dictionary.")
        return jsonify({"error": "The report parser returned an invalid result."}), 500

    required_parser_fields = {"depth_cm", "severity", "confidence", "needs_review"}
    if not required_parser_fields.issubset(parsed):
        missing = ", ".join(sorted(required_parser_fields.difference(parsed)))
        app.logger.error("The parser result is missing fields: %s", missing)
        return jsonify({"error": "The report parser returned an incomplete result."}), 500

    depth_cm = parsed["depth_cm"]
    severity = parsed["severity"]
    confidence = parsed["confidence"]
    needs_review = parsed["needs_review"]
    if depth_cm is not None and not _valid_depth(depth_cm):
        return jsonify({"error": "The parser returned an invalid depth_cm value."}), 500
    if not isinstance(severity, str) or not severity.strip():
        return jsonify({"error": "The parser returned an invalid severity value."}), 500
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
    ):
        return jsonify({"error": "The parser returned an invalid confidence value."}), 500
    if not isinstance(needs_review, bool):
        return jsonify({"error": "The parser returned an invalid needs_review value."}), 500

    now = _now()
    report = {
        "id": str(uuid.uuid4()),
        "area": area.strip(),
        "text": text.strip(),
        "depth_cm": depth_cm,
        "severity": severity.strip(),
        "confidence": confidence,
        "needs_review": needs_review,
        "created_at": now.isoformat().replace("+00:00", "Z"),
    }

    try:
        add_report(report)
        all_reports = get_all_reports()
        conflicts = _find_conflicts(all_reports)
        public_report = next(
            item for item in _public_reports(all_reports, now, conflicts)
            if item["id"] == report["id"]
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        app.logger.exception("Could not save the flood report.")
        return jsonify({"error": f"Could not save report: {error}"}), 500

    return jsonify(public_report), 201


@app.get("/api/reports")
def list_reports():
    reports, error_response = _load_reports_or_error()
    if error_response:
        return error_response

    try:
        conflicts = _find_conflicts(reports)
        return jsonify(_public_reports(reports, _now(), conflicts))
    except (KeyError, TypeError, ValueError) as error:
        app.logger.exception("Stored reports could not be processed.")
        return jsonify({"error": f"Stored reports are invalid: {error}"}), 500


@app.get("/api/summary")
def get_summary():
    reports, error_response = _load_reports_or_error()
    if error_response:
        return error_response

    now = _now()
    try:
        conflicts = _find_conflicts(reports)
        area_summaries = _area_summaries(reports, now, conflicts)
        old_count = sum(_report_is_old(report, now) for report in reports)
    except (KeyError, TypeError, ValueError) as error:
        app.logger.exception("Stored reports could not be summarized.")
        return jsonify({"error": f"Stored reports are invalid: {error}"}), 500

    return jsonify({
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "total_reports": len(reports),
        "recent_report_count": len(reports) - old_count,
        "old_report_count": old_count,
        "area_count": len(area_summaries),
        "conflict_count": len(conflicts),
        "areas": area_summaries,
        "worst_areas": area_summaries[:MAX_WORST_AREAS],
        "conflicts": conflicts,
    })


if parse_report is None:
    app.logger.warning(
        "report_parser.py is not available; POST /api/reports will return HTTP 503."
    )


if __name__ == "__main__":
    app.run(debug=False)
