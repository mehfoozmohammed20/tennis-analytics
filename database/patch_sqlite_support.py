"""
Patch for app/streamlit_app.py so it works on the hosted (SQLite snapshot) version too.

What it changes (your other edits stay untouched):
  1. imports backend_label from database/connection.py
  2. shows a sidebar line: "Data source: MySQL (live)" or "Data source: saved snapshot (date)"
  3. points / competitions_played is divided as decimals (SQLite would otherwise round down to whole numbers)

All-or-nothing: if any anchor line is not found, NOTHING is changed.
Usage (from the project folder):   python patch_sqlite_support.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "app", "streamlit_app.py")

EDITS = [
    ("from database.connection import get_connection\n",
     "from database.connection import backend_label, get_connection\n"),
    ('st.sidebar.title("🎾 Tennis Analytics")\n',
     'st.sidebar.title("🎾 Tennis Analytics")\nst.sidebar.caption(backend_label())\n'),
    ("ROUND(r.points / NULLIF(r.competitions_played, 0), 1) AS points_per_competition",
     "ROUND(r.points * 1.0 / NULLIF(r.competitions_played, 0), 1) AS points_per_competition"),
    ("SELECT AVG(r.points / r.competitions_played) AS n",
     "SELECT AVG(r.points * 1.0 / r.competitions_played) AS n"),
]

if not os.path.exists(target):
    sys.exit(f"File not found: {target}\nRun this from the project folder, or pass the path: python patch_sqlite_support.py path\\to\\streamlit_app.py")

with open(target, "r", encoding="utf-8") as f:
    text = f.read()

if "backend_label" in text:
    sys.exit("Already patched - nothing to do.")

for i, (old, _) in enumerate(EDITS, 1):
    if text.count(old) != 1:
        sys.exit(f"Could not find the exact lines for edit {i} of {len(EDITS)} (the file may have been edited there). "
                 "No changes were made.")

new_text = text
for old, new in EDITS:
    new_text = new_text.replace(old, new)

shutil.copyfile(target, target + ".bak4")
with open(target, "w", encoding="utf-8") as f:
    f.write(new_text)
print(f"Patched OK ({len(EDITS)} edits). Backup saved as {target}.bak4")
