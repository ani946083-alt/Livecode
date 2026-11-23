"""
report_parser.py  -  FloodWatch (Member 2: Report Processing Developer)

Turns a volunteer's flood report written in plain English into
structured data:

    {
        "depth_cm":     number or None,
        "severity":     "Low" / "Moderate" / "High" / "Critical" / "Unknown",
        "confidence":   "high" / "medium" / "low",
        "needs_review": True / False,
        "reason":       short sentence explaining the decision
    }

Golden rule: if the report is unclear, we say None / Unknown.
We NEVER invent an exact depth.

Works with Python 3.9 (standard library only).
"""

import re

# ---------------------------------------------------------------
# 1. Conversion numbers (everything is converted to centimeters)
# ---------------------------------------------------------------
CM_PER_FOOT = 30.48
CM_PER_INCH = 2.54
CM_PER_METER = 100

# ---------------------------------------------------------------
# 2. Body-landmark words -> depth in cm
#    (ankle and knee come from the project brief; waist is a
#    common approximation)
# ---------------------------------------------------------------
BODY_LANDMARKS = [
    ("ankle deep", r"ankle (?:deep|high)", 10),
    ("knee deep", r"knee (?:deep|high)", 50),
    ("waist deep", r"waist (?:deep|high)", 100),
]

# "Rickshaw can barely pass" tells us the water is serious, but it does
# NOT give a real measurement, so depth stays None (not invented).
RICKSHAW_PATTERN = r"rickshaws? (?:can )?(?:barely|hardly|just about) (?:pass|move|go)"

ROAD_CLOSED_PATTERN = r"road (?:is |has been |was )?closed|closed road|road closure"

# Anything deeper than this is probably a typo (e.g. 500 cm = 5 meters)
SUSPICIOUS_DEPTH_CM = 300

# ---------------------------------------------------------------
# 3. Regular expressions for measurements like "1.5 feet"
# ---------------------------------------------------------------
NUMBER = r"(\d+(?:\.\d+)?)"

FEET_UNIT = r"(?:feet|foot|ft|')"
# a bare "in" is only accepted at the end of a sentence ("20 in.")
# so that "3 in the road" is not read as 3 inches
INCH_UNIT = r"(?:inches|inch|in(?=\s*(?:$|[.,;!?]))|\")"
CM_UNIT = r"(?:centimeters|centimetres|centimeter|centimetre|cm)"
METER_UNIT = r"(?:meters|metres|meter|metre|m)"


def _unit_pattern(unit):
    # number + optional spaces + unit, and the unit must not be
    # followed by another letter (so "5 minutes" is not "5 m")
    return re.compile(NUMBER + r"\s*" + unit + r"(?![a-z])")


# "5 feet 6 inches" / "5'6\"" (checked first so we can add them together)
FEET_AND_INCHES = re.compile(
    NUMBER + r"\s*" + FEET_UNIT + r"\s*(?:and\s*)?" + NUMBER + r"\s*" + INCH_UNIT + r"(?![a-z])"
)

SINGLE_UNITS = [
    (_unit_pattern(FEET_UNIT), CM_PER_FOOT),
    (_unit_pattern(INCH_UNIT), CM_PER_INCH),
    (_unit_pattern(CM_UNIT), 1),
    (_unit_pattern(METER_UNIT), CM_PER_METER),
]


# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------
def _clean_text(text):
    """Lowercase, fix fancy quotes, replace hyphens, trim extra spaces."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("-", " ")
    return " ".join(text.split())


def _find_measurements(text):
    """Find every 'number + unit' in the text. Returns a list of cm values."""
    found = []

    # step 1: "5 feet 6 inches" -> one value, then blank it out of the text
    def handle_feet_and_inches(match):
        feet = float(match.group(1))
        inches = float(match.group(2))
        found.append(round(feet * CM_PER_FOOT + inches * CM_PER_INCH, 2))
        return " "

    text = FEET_AND_INCHES.sub(handle_feet_and_inches, text)

    # step 2: single measurements like "20 inches" or "1.5 feet"
    for pattern, cm_per_unit in SINGLE_UNITS:
        for match in pattern.finditer(text):
            found.append(round(float(match.group(1)) * cm_per_unit, 2))

    return found


def _find_landmarks(text):
    """Find words like 'knee deep'. Returns a list of cm values."""
    found = []
    for _name, pattern, depth_cm in BODY_LANDMARKS:
        if re.search(pattern, text):
            found.append(depth_cm)
    return found


def severity_from_depth(depth_cm):
    """Turn a depth in cm into a severity word."""
    if depth_cm is None:
        return "Unknown"
    if depth_cm < 15:
        return "Low"
    if depth_cm < 50:
        return "Moderate"
    if depth_cm < 100:
        return "High"
    return "Critical"


def _clean_number(value):
    """Show 50.0 as 50 but keep 45.72 as 45.72."""
    if value is None:
        return None
    value = round(value, 2)
    if value == int(value):
        return int(value)
    return value


# ---------------------------------------------------------------
# Main function
# ---------------------------------------------------------------
def parse_report(text):
    """Read one volunteer report and return a result dictionary."""
    clean = _clean_text(text)

    road_closed = re.search(ROAD_CLOSED_PATTERN, clean) is not None
    rickshaw = re.search(RICKSHAW_PATTERN, clean) is not None
    measurements = _find_measurements(clean)
    landmarks = _find_landmarks(clean)

    # Start from "we know nothing" and only improve it with real evidence.
    depth_cm = None
    confidence = "low"
    needs_review = True
    reason = "No clear water depth found in the report."

    if measurements:
        # Case A: the volunteer gave a real measurement (best information)
        depth_cm = max(measurements)
        if len(set(measurements)) == 1:
            confidence = "high"
            needs_review = False
            reason = "Clear measurement found in the report."
        else:
            confidence = "medium"
            needs_review = True
            reason = "Several different measurements found; used the deepest."

    elif landmarks:
        # Case B: body landmark such as "knee deep" (an estimate)
        depth_cm = max(landmarks)
        if len(set(landmarks)) == 1:
            confidence = "medium"
            needs_review = False
            reason = "Depth estimated from a body landmark."
        else:
            confidence = "low"
            needs_review = True
            reason = "Mixed landmarks (e.g. ankle and knee); used the deepest."

    elif rickshaw:
        # Case C: serious, but no real number -> do NOT invent one
        confidence = "medium"
        needs_review = True
        reason = "Rickshaw struggling to pass means deep water, but no exact depth given."

    severity = severity_from_depth(depth_cm)
    if depth_cm is None and rickshaw:
        severity = "High"

    # Road closed always means Critical.
    if road_closed:
        severity = "Critical"
        if depth_cm is None and not rickshaw:
            confidence = "high"
            needs_review = False
            reason = "Road is closed, so severity is Critical (depth not reported)."
        else:
            reason += " Road is closed, so severity is Critical."

    # Safety check: a huge number is probably a typing mistake.
    if depth_cm is not None and depth_cm > SUSPICIOUS_DEPTH_CM:
        confidence = "low"
        needs_review = True
        reason += " Depth is unusually large, please double-check."

    return {
        "depth_cm": _clean_number(depth_cm),
        "severity": severity,
        "confidence": confidence,
        "needs_review": needs_review,
        "reason": reason,
    }
