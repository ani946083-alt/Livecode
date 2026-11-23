import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import app
from report_parser import parse_report


def make_report(area, depth, severity, minutes_ago, report_id):
    created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "id": report_id,
        "road_name": area,
        "area": area,
        "text": f"{depth} cm",
        "depth_cm": depth,
        "severity": severity,
        "confidence": 0.9,
        "needs_review": False,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
    }


class ReportParserTests(unittest.TestCase):
    def test_parses_bengali_qualitative_depth(self):
        parsed = parse_report("হাঁটু পানি")

        self.assertEqual(parsed["depth_cm"], 45)
        self.assertTrue(parsed["needs_review"])

    def test_converts_non_latin_digits_and_spanish_units(self):
        self.assertEqual(parse_report("१.५ फुट")["depth_cm"], 45.7)
        self.assertEqual(parse_report("1,5 pies")["depth_cm"], 45.7)
        self.assertEqual(parse_report("١٫٥ متر")["depth_cm"], 150)
        self.assertEqual(parse_report("hasta la rodilla")["depth_cm"], 45)

    def test_marks_unrecognized_language_for_review(self):
        parsed = parse_report("unrecognized report wording")

        self.assertIsNone(parsed["depth_cm"])
        self.assertTrue(parsed["needs_review"])


class FloodWatchApiTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_dashboard_is_served_by_flask(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="roads-list"', response.data)
        response.close()

    def test_report_submission_saves_road_name_and_parsed_depth(self):
        saved_reports = []
        with (
            patch("app.add_report", side_effect=saved_reports.append),
            patch("app.get_all_reports", side_effect=lambda: saved_reports),
        ):
            response = self.client.post(
                "/api/reports",
                json={
                    "road_name": "College Road",
                    "area": "North",
                    "text": "1.5 feet of water",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["road_name"], "College Road")
        self.assertEqual(response.json["depth_cm"], 45.7)

    def test_summary_reconciles_conflicts_and_ignores_old_reports(self):
        reports = [
            make_report("River Road", 15, "low", 10, "new-low"),
            make_report(" river   road ", 60, "high", 5, "new-high"),
            make_report("Old Road", 200, "severe", 120, "old"),
        ]
        with patch("app.get_all_reports", return_value=reports):
            response = self.client.get("/api/summary")

        self.assertEqual(response.status_code, 200)
        summary = response.json
        self.assertEqual(summary["old_report_count"], 1)
        self.assertEqual(summary["recent_report_count"], 2)
        self.assertEqual(summary["conflict_count"], 1)
        self.assertEqual(summary["area_count"], 1)
        worst_area = summary["worst_areas"][0]
        self.assertEqual(worst_area["area"], "river road")
        self.assertEqual(worst_area["depth_cm"], 37.5)
        self.assertEqual(worst_area["status"], "high")
        self.assertTrue(worst_area["has_conflict"])
        self.assertTrue(worst_area["needs_review"])


if __name__ == "__main__":
    unittest.main()
