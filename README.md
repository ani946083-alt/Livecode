# FloodWatch-Parser

**FloodWatch – Real-Time Water Depth Monitoring System**
Member 2: Report Processing Developer

This module reads a volunteer's flood report written in plain English and turns it
into structured data (depth in centimeters, severity, confidence, and whether a
human should double-check it).

- Python 3.9.6 compatible
- Standard library only (nothing to install)
- No Flask, no database, no API

## Folder structure

```
FloodWatch-Parser/
├── report_parser.py   <- the parse_report(text) function
├── test_parser.py     <- unit tests (23 tests)
├── main.py            <- interactive terminal app
├── README.md
└── requirements.txt   <- empty on purpose (no packages needed)
```

## How to run (VS Code)

1. Open VS Code -> **File -> Open Folder...** -> choose `FloodWatch-Parser`.
2. Open the terminal: **Terminal -> New Terminal**.
3. Run the app:

```
python main.py
```

(On macOS/Linux use `python3 main.py` if `python` does not work.)

4. Run the tests:

```
python -m unittest -v
```

You should see `Ran 23 tests ... OK`.

## Using the function in code

```python
from report_parser import parse_report

print(parse_report("Water is 1.5 feet deep"))
# {'depth_cm': 45.72, 'severity': 'Moderate', 'confidence': 'high',
#  'needs_review': False, 'reason': 'Clear measurement found in the report.'}
```

`parse_report` returns a dictionary with:

| Key            | Meaning                                                         |
|----------------|-----------------------------------------------------------------|
| `depth_cm`     | Depth in centimeters, or `None` if it cannot be known           |
| `severity`     | `Low`, `Moderate`, `High`, `Critical` or `Unknown`              |
| `confidence`   | `high` (real measurement), `medium` (estimate), `low` (unclear) |
| `needs_review` | `True` if a human should check the report                       |
| `reason`       | (extra) one sentence explaining the decision                    |

## What it understands

| Report text                     | depth_cm | severity | confidence | needs_review |
|---------------------------------|----------|----------|------------|--------------|
| `Ankle deep`                    | 10       | Low      | medium     | False        |
| `Knee deep`                     | 50       | High     | medium     | False        |
| `Waist deep`                    | 100      | Critical | medium     | False        |
| `1.5 feet`                      | 45.72    | Moderate | high       | False        |
| `20 inches`                     | 50.8     | High     | high       | False        |
| `30 cm`                         | 30       | Moderate | high       | False        |
| `1.2 meters`                    | 120      | Critical | high       | False        |
| `1 foot 6 inches`               | 45.72    | Moderate | high       | False        |
| `Road closed`                   | None     | Critical | high       | False        |
| `Rickshaw can barely pass`      | None     | High     | medium     | True         |
| `Water getting deeper`          | None     | Unknown  | low        | True         |

### Conversions used

- 1 foot = 30.48 cm
- 1 inch = 2.54 cm
- 1 meter = 100 cm
- Ankle deep = 10 cm, Knee deep = 50 cm, Waist deep = 100 cm

### Severity levels

| Depth          | Severity |
|----------------|----------|
| under 15 cm    | Low      |
| 15 to 49 cm    | Moderate |
| 50 to 99 cm    | High     |
| 100 cm or more | Critical |
| Road closed    | Critical (always) |

## The "never invent a depth" rule

If the report does not contain a real measurement or a clear body landmark,
`depth_cm` is `None` and `needs_review` is `True`. Examples:

- `Water getting deeper` -> depth `None`, severity `Unknown`
- `water level 30` -> depth `None` (a number with no unit is not guessed)
- `Rickshaw can barely pass` -> depth `None`, severity `High` (serious, but no real number)

Other safety checks:

- Two different measurements in one report -> uses the deepest, confidence `medium`, `needs_review` True
- Mixed landmarks ("ankle deep here, knee deep there") -> confidence `low`, `needs_review` True
- A depth over 300 cm is probably a typo -> confidence `low`, `needs_review` True
- `5 minutes` or `3 in the road` are NOT read as measurements

## Sample session

```
Area name: Mirpur
Flood report: Knee deep

---------- Result for: Mirpur ----------
Depth        : 50 cm
Severity     : High
Confidence   : medium
Needs review : No
Reason       : Depth estimated from a body landmark.
--------------------------------------------

Area name: Motijheel
Flood report: Road closed

---------- Result for: Motijheel ----------
Depth        : Unknown (not enough information)
Severity     : Critical
Confidence   : high
Needs review : No
Reason       : Road is closed, so severity is Critical (depth not reported).
--------------------------------------------

Area name: Uttara
Flood report: Water getting deeper

---------- Result for: Uttara ----------
Depth        : Unknown (not enough information)
Severity     : Unknown
Confidence   : low
Needs review : YES - please check this report
Reason       : No clear water depth found in the report.
--------------------------------------------
```

## How the code works (for explaining it)

`parse_report(text)` follows these steps:

1. **Clean** the text (lowercase, remove hyphens, tidy spaces).
2. **Look for real measurements** like `1.5 feet` using regular expressions and convert to cm.
3. **If none, look for body landmarks** like `knee deep`.
4. **If none, check for "rickshaw can barely pass"** (serious, but no number).
5. **Check "road closed"** -> severity becomes Critical.
6. **Safety check** for impossibly large depths.
7. **Return** the dictionary.

Order of trust: real measurement (high) > body landmark (medium) > unclear (low).

## Known limitations

- Numbers written as words ("two feet") are not understood yet; they are treated as unclear and flagged for review.
- Only English reports are supported.
