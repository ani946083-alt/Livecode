# Livecode

## Run FloodWatch locally

From the `Livecode` directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Flask serves both the dashboard and its API from the same origin. If port 5000 is already in use, run `PORT=5001 python app.py` and open <http://127.0.0.1:5001>.

Reports are stored locally in `data/reports.json`. The parser recognizes common depth units and qualitative depth phrases in Bengali, English, Hindi, Spanish, French, and Arabic. Unknown or ambiguous wording is marked for review instead of being assigned a made-up depth. This rule-based parser cannot guarantee understanding of every language or dialect.

Reports older than 60 minutes are excluded from the current area ranking. Fresh reports for an area are summarized using the median parsed depth; reports at least 20 cm apart within 30 minutes are flagged as conflicts and require review. The dashboard refreshes automatically once per minute.

Run the focused checks with `python -m unittest discover -s tests -v`.