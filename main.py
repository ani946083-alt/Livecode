"""
main.py  -  simple terminal interface for the FloodWatch report parser

Run with:
    python main.py
Type  quit  (or press Ctrl+C) to stop.
"""

from report_parser import parse_report


def show_result(area, result):
    """Print the parsed result in a readable way."""
    if result["depth_cm"] is None:
        depth_text = "Unknown (not enough information)"
    else:
        depth_text = "{} cm".format(result["depth_cm"])

    if result["needs_review"]:
        review_text = "YES - please check this report"
    else:
        review_text = "No"

    print()
    print("---------- Result for: {} ----------".format(area))
    print("Depth        : {}".format(depth_text))
    print("Severity     : {}".format(result["severity"]))
    print("Confidence   : {}".format(result["confidence"]))
    print("Needs review : {}".format(review_text))
    print("Reason       : {}".format(result["reason"]))
    print("-" * 44)
    print()


def main():
    print("=" * 44)
    print("  FloodWatch - Volunteer Report Parser")
    print("=" * 44)
    print("Type 'quit' at any prompt to exit.")
    print("Example reports: 'knee deep', '1.5 feet', 'road closed'")
    print()

    while True:
        try:
            area = input("Area name: ").strip()
            if area.lower() == "quit":
                break
            if area == "":
                area = "Unnamed area"

            report = input("Flood report: ").strip()
            if report.lower() == "quit":
                break
        except (KeyboardInterrupt, EOFError):
            print()
            break

        show_result(area, parse_report(report))

    print("Goodbye! Stay safe.")


if __name__ == "__main__":
    main()
