"""
app.py  –  FloodWatch REST API
================================
Entry point for the Flask application.

Start the server:
    python app.py

Endpoints:
    POST /api/reports    – Submit a new flood report
    GET  /api/reports    – Retrieve all stored reports
    GET  /api/summary    – Get a statistical overview of flood data
"""

from flask import Flask, request, jsonify

import database

# ---------------------------------------------------------------------------
# Parser import
# ---------------------------------------------------------------------------
# We attempt to import the teammate's parser at startup.
# If report_parser.py is not present yet, the app still starts cleanly.
# POST /api/reports will return 503 until the file is added and the server
# is restarted. All GET endpoints work without the parser.

try:
    from report_parser import parse_report
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Input length limits  (security: prevent huge strings from bloating the file)
# ---------------------------------------------------------------------------
MAX_AREA_LENGTH = 200    # characters
MAX_TEXT_LENGTH = 1000   # characters


# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Utility: uniform JSON error response
# ---------------------------------------------------------------------------

def make_error(message, status_code):
    """
    Return a consistent JSON error response.

    Every error from this API has the same shape:
        { "error": "<human-readable message>" }

    Args:
        message     (str): Description of what went wrong.
        status_code (int): HTTP status code (400, 404, 500, 503 …).

    Returns:
        tuple: (Flask Response, int) – Flask unpacks this as (body, status).
    """
    # str() ensures we never accidentally serialise a non-string object
    return jsonify({"error": str(message)}), status_code


# ---------------------------------------------------------------------------
# Utility: validate the dict returned by parse_report()
# ---------------------------------------------------------------------------

def _validate_parsed(parsed):
    """
    Verify that parse_report() returned a dict with all required keys and
    correct value types.

    Args:
        parsed (dict): Return value from parse_report().

    Returns:
        str | None: An error message string if validation fails, else None.
    """
    # --- Key presence check ---
    required_keys = {"depth_cm", "severity", "confidence", "needs_review"}
    missing = required_keys - set(parsed.keys())
    if missing:
        return (
            f"Parser returned incomplete data. "
            f"Missing keys: {sorted(missing)}"
        )

    # --- Type checks ---

    # depth_cm: must be a number (int or float); bool is a subclass of int
    # so we exclude it explicitly to avoid True/False being accepted.
    if not isinstance(parsed["depth_cm"], (int, float)) or isinstance(
        parsed["depth_cm"], bool
    ):
        return "Parser returned invalid 'depth_cm' – must be a number."

    if parsed["depth_cm"] < 0:
        return "Parser returned invalid 'depth_cm' – must be >= 0."

    # severity: must be a non-empty string
    if not isinstance(parsed["severity"], str) or not parsed["severity"].strip():
        return "Parser returned invalid 'severity' – must be a non-empty string."

    # confidence: accept int or float (e.g. confidence=1 is valid)
    if not isinstance(parsed["confidence"], (int, float)) or isinstance(
        parsed["confidence"], bool
    ):
        return "Parser returned invalid 'confidence' – must be a number."

    # needs_review: must be a boolean
    if not isinstance(parsed["needs_review"], bool):
        return (
            "Parser returned invalid 'needs_review' – must be true or false."
        )

    return None  # all good


# ===========================================================================
# ROUTE 1 – POST /api/reports
# ===========================================================================

@app.route("/api/reports", methods=["POST"])
def create_report():
    """
    Submit a new flood report.

    Request body (JSON):
        {
            "area": "School Road",
            "text": "Water up to my knees"
        }

    Success response – HTTP 201:
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

    Error responses:
        400 – Missing / empty fields, oversized input, invalid JSON body
        503 – report_parser.py not yet available
        500 – Unexpected server error
    """

    # ----- Step 1: Check parser availability --------------------------------
    if not PARSER_AVAILABLE:
        return make_error(
            "Parser integration is not complete. "
            "Place report_parser.py (provided by your teammate) in the "
            "backend/ folder and restart the server. "
            "GET /api/reports and GET /api/summary work without the parser.",
            503,
        )

    # ----- Step 2: Parse JSON body -----------------------------------------
    # force=False: only parse when Content-Type is application/json.
    # silent=True: return None instead of raising on bad JSON.
    data = request.get_json(silent=True, force=False)

    if data is None:
        return make_error(
            "Request body is missing or not valid JSON. "
            "Set Content-Type to 'application/json' and send a JSON object.",
            400,
        )

    # Guard: the body must be a JSON object (dict), not an array or scalar
    if not isinstance(data, dict):
        return make_error(
            "Request body must be a JSON object "
            "({\"area\": \"...\", \"text\": \"...\"}).",
            400,
        )

    # ----- Step 3: Extract and validate fields ------------------------------
    area = data.get("area")
    text = data.get("text")

    # -- Presence checks --
    if area is None:
        return make_error("Missing required field: 'area'.", 400)

    if text is None:
        return make_error("Missing required field: 'text'.", 400)

    # -- Type checks --
    if not isinstance(area, str):
        return make_error("Field 'area' must be a string.", 400)

    if not isinstance(text, str):
        return make_error("Field 'text' must be a string.", 400)

    # -- Whitespace / empty checks --
    area = area.strip()
    text = text.strip()

    if not area:
        return make_error("Field 'area' must not be empty or whitespace.", 400)

    if not text:
        return make_error("Field 'text' must not be empty or whitespace.", 400)

    # -- Length limits (security: prevent file bloat) --
    if len(area) > MAX_AREA_LENGTH:
        return make_error(
            f"Field 'area' exceeds the maximum allowed length "
            f"of {MAX_AREA_LENGTH} characters.",
            400,
        )

    if len(text) > MAX_TEXT_LENGTH:
        return make_error(
            f"Field 'text' exceeds the maximum allowed length "
            f"of {MAX_TEXT_LENGTH} characters.",
            400,
        )

    # ----- Step 4: Call the parser -----------------------------------------
    try:
        parsed = parse_report(text)
    except Exception as exc:
        # Log the full traceback server-side; return a safe message to client
        app.logger.error(
            "parse_report() raised an exception.", exc_info=True
        )
        return make_error(
            f"The parser encountered an error: {str(exc)}", 500
        )

    # Guard: parser must return a dict
    if not isinstance(parsed, dict):
        app.logger.error(
            "parse_report() returned %s instead of a dict.", type(parsed).__name__
        )
        return make_error(
            "Parser returned an unexpected type. Expected a dict.", 500
        )

    # ----- Step 5: Validate parser output ----------------------------------
    validation_error = _validate_parsed(parsed)
    if validation_error:
        app.logger.error(
            "Parser output failed validation: %s | parsed=%s",
            validation_error, parsed,
        )
        return make_error(validation_error, 500)

    # ----- Step 6: Store the report ----------------------------------------
    try:
        report = database.add_report(area, text, parsed)
    except (IOError, ValueError) as exc:
        app.logger.error("database.add_report() failed.", exc_info=True)
        return make_error(f"Failed to save report: {str(exc)}", 500)

    return jsonify(report), 201


# ===========================================================================
# ROUTE 2 – GET /api/reports
# ===========================================================================

@app.route("/api/reports", methods=["GET"])
def get_reports():
    """
    Return every stored report as a JSON array.

    is_old flags are recalculated on every call, so the client always
    receives up-to-date staleness information.

    Success response – HTTP 200:
        [{ "id": 1, "area": "...", ... }, ...]
        Returns [] when no reports have been submitted yet.

    Error response:
        500 – File read or write error.
    """
    try:
        reports = database.get_all_reports()
    except (IOError, ValueError) as exc:
        app.logger.error("get_all_reports() failed.", exc_info=True)
        return make_error(f"Failed to load reports: {str(exc)}", 500)

    return jsonify(reports), 200


# ===========================================================================
# ROUTE 3 – GET /api/summary
# ===========================================================================

@app.route("/api/summary", methods=["GET"])
def get_summary():
    """
    Return a statistical summary of the current flood situation.

    Success response – HTTP 200:
        {
            "total_reports":       5,
            "active_reports":      3,
            "old_reports":         2,
            "conflict_reports":    1,
            "worst_flooded_areas": [
                { "area": "School Road",   "max_depth_cm": 90 },
                { "area": "Market Street", "max_depth_cm": 55 }
            ]
        }

    Field definitions:
        total_reports     – Every report ever submitted.
        active_reports    – Reports from the last 60 minutes.
        old_reports       – Reports older than 60 minutes.
                            Note: active_reports + old_reports == total_reports.
        conflict_reports  – Count of reports involved in a conflict.
        worst_flooded_areas – Active areas sorted by highest depth, deepest first.

    Error response:
        500 – File read or write error.
    """
    try:
        # get_all_reports() loads from disk and refreshes is_old in one call
        all_reports = database.get_all_reports()

        active    = database.get_active_reports(all_reports)
        old       = database.get_old_reports(all_reports)
        conflicts = database.get_conflict_reports(all_reports)
        worst     = database.get_worst_flooded_areas(active)

        summary = {
            "total_reports":       len(all_reports),
            "active_reports":      len(active),
            "old_reports":         len(old),
            "conflict_reports":    len(conflicts),
            "worst_flooded_areas": worst,
        }

    except (IOError, ValueError) as exc:
        app.logger.error("get_summary() failed.", exc_info=True)
        return make_error(f"Failed to generate summary: {str(exc)}", 500)

    return jsonify(summary), 200


# ===========================================================================
# Global HTTP error handlers
# ===========================================================================
# These turn Flask's default HTML error pages into JSON responses,
# keeping the API consistent for all callers.
#
# Note on 500: in debug=True mode, Flask's Werkzeug debugger intercepts
# unhandled exceptions before this handler fires. That is expected behaviour –
# the debugger gives useful tracebacks during development. In production
# (debug=False), this handler returns a clean JSON 500 response.

@app.errorhandler(404)
def not_found(_error):
    """Return JSON 404 instead of Flask's default HTML page."""
    return make_error(
        "Endpoint not found. "
        "Available: POST /api/reports | GET /api/reports | GET /api/summary",
        404,
    )


@app.errorhandler(405)
def method_not_allowed(_error):
    """Return JSON 405 when the wrong HTTP verb is used on a known route."""
    return make_error("HTTP method not allowed on this endpoint.", 405)


@app.errorhandler(500)
def internal_error(_error):
    """Return JSON 500 for any unhandled server-side exception."""
    return make_error("An unexpected server error occurred.", 500)


# ===========================================================================
# Run
# ===========================================================================

if __name__ == "__main__":
    # SECURITY NOTE:
    # host="0.0.0.0" makes the server reachable from other machines on your
    # network. This is intentional for local team testing. Do NOT expose this
    # to the internet without authentication and debug=False.
    #
    # debug=True enables auto-reload on code changes and detailed error pages.
    # Always set debug=False before any real deployment.
    app.run(debug=True, host="0.0.0.0", port=5000)
