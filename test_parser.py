"""
test_parser.py  -  tests for report_parser.parse_report

Run with:
    python -m unittest -v
(uses only the built-in unittest module, nothing to install)
"""

import unittest

from report_parser import parse_report


class TestUnits(unittest.TestCase):
    """Real measurements -> centimeters."""

    def test_feet(self):
        result = parse_report("Water is 1.5 feet deep")
        self.assertEqual(result["depth_cm"], 45.72)
        self.assertEqual(result["severity"], "Moderate")
        self.assertEqual(result["confidence"], "high")
        self.assertFalse(result["needs_review"])

    def test_inches(self):
        result = parse_report("20 inches of water near the market")
        self.assertEqual(result["depth_cm"], 50.8)
        self.assertEqual(result["severity"], "High")

    def test_centimeters(self):
        result = parse_report("about 30 cm")
        self.assertEqual(result["depth_cm"], 30)
        self.assertEqual(result["severity"], "Moderate")

    def test_meters(self):
        result = parse_report("water is 1.2 meters high")
        self.assertEqual(result["depth_cm"], 120)
        self.assertEqual(result["severity"], "Critical")

    def test_short_units(self):
        self.assertEqual(parse_report("2 ft")["depth_cm"], 60.96)
        self.assertEqual(parse_report("1 m")["depth_cm"], 100)

    def test_feet_and_inches_together(self):
        result = parse_report("It is 1 foot 6 inches deep")
        self.assertEqual(result["depth_cm"], 45.72)

    def test_uppercase_text(self):
        self.assertEqual(parse_report("20 INCHES")["depth_cm"], 50.8)


class TestLandmarks(unittest.TestCase):
    """Body-landmark words."""

    def test_ankle_deep(self):
        result = parse_report("Ankle deep")
        self.assertEqual(result["depth_cm"], 10)
        self.assertEqual(result["severity"], "Low")
        self.assertEqual(result["confidence"], "medium")

    def test_knee_deep(self):
        result = parse_report("Knee deep")
        self.assertEqual(result["depth_cm"], 50)
        self.assertEqual(result["severity"], "High")

    def test_knee_deep_with_hyphen(self):
        self.assertEqual(parse_report("knee-deep water")["depth_cm"], 50)

    def test_waist_deep(self):
        result = parse_report("Waist deep near the bridge")
        self.assertEqual(result["depth_cm"], 100)
        self.assertEqual(result["severity"], "Critical")

    def test_mixed_landmarks_need_review(self):
        result = parse_report("ankle deep in some places, knee deep in others")
        self.assertEqual(result["confidence"], "low")
        self.assertTrue(result["needs_review"])


class TestSpecialPhrases(unittest.TestCase):
    """Road closed and rickshaw reports."""

    def test_road_closed(self):
        result = parse_report("Road closed")
        self.assertEqual(result["severity"], "Critical")
        self.assertIsNone(result["depth_cm"])
        self.assertFalse(result["needs_review"])

    def test_road_closed_with_depth(self):
        result = parse_report("Road is closed, knee deep water")
        self.assertEqual(result["severity"], "Critical")
        self.assertEqual(result["depth_cm"], 50)

    def test_rickshaw_barely_pass(self):
        result = parse_report("Rickshaw can barely pass")
        self.assertIsNone(result["depth_cm"])  # never invented
        self.assertEqual(result["severity"], "High")
        self.assertTrue(result["needs_review"])


class TestUnclearReports(unittest.TestCase):
    """The parser must NOT guess when the report is unclear."""

    def test_getting_deeper(self):
        result = parse_report("Water getting deeper")
        self.assertIsNone(result["depth_cm"])
        self.assertEqual(result["severity"], "Unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertTrue(result["needs_review"])

    def test_number_without_unit(self):
        result = parse_report("water level 30")
        self.assertIsNone(result["depth_cm"])
        self.assertTrue(result["needs_review"])

    def test_not_a_measurement(self):
        # "5 minutes" and "3 in the road" must not become 5 m / 3 inches
        self.assertIsNone(parse_report("waited 5 minutes")["depth_cm"])
        self.assertIsNone(parse_report("3 in the road")["depth_cm"])

    def test_empty_text(self):
        result = parse_report("")
        self.assertIsNone(result["depth_cm"])
        self.assertEqual(result["severity"], "Unknown")
        self.assertTrue(result["needs_review"])

    def test_not_a_string(self):
        result = parse_report(None)
        self.assertIsNone(result["depth_cm"])
        self.assertTrue(result["needs_review"])

    def test_conflicting_measurements(self):
        result = parse_report("1 foot in one place and 2 feet in another")
        self.assertEqual(result["depth_cm"], 60.96)
        self.assertEqual(result["confidence"], "medium")
        self.assertTrue(result["needs_review"])

    def test_suspicious_huge_depth(self):
        result = parse_report("500 cm of water")
        self.assertEqual(result["confidence"], "low")
        self.assertTrue(result["needs_review"])


class TestResultShape(unittest.TestCase):
    def test_all_keys_present(self):
        result = parse_report("knee deep")
        for key in ("depth_cm", "severity", "confidence", "needs_review"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
