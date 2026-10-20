"""
Adds an "Exclude 'Neutral'" tick-box to the Rankings page country analysis.
When ticked, 'Neutral' (not a real country) is left out of BOTH country charts
(Average points by country, Total points by country) and their counts and shares.
Off by default, so existing numbers do not change until you tick it.

All-or-nothing: if any anchor line is not found, NOTHING is changed.
Your other edits stay untouched.
Usage (from the project folder):   python patch_exclude_neutral.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "app", "streamlit_app.py")

EDITS = [
    # 1) the tick-box, placed right after the minimum-sample slider
    (
        '''                          help="Hides countries with very few competitors so a 1–2 player country can't top the average.")
''',
        '''                          help="Hides countries with very few competitors so a 1–2 player country can't top the average.")
        exclude_neutral = st.checkbox(
            "Exclude 'Neutral' (not a real country)", value=False,
            help="'Neutral' is a value in the data's country field for competitors without a national affiliation. "
                 "Tick this to compare real countries only.")
        neutral_sql = " AND co.country <> 'Neutral'" if exclude_neutral else ""
        neutral_note = " (excluding Neutral)" if exclude_neutral else ""
''',
    ),
    # 2) average points chart query
    (
        '''            WHERE {LATEST_SNAPSHOT}
            GROUP BY co.country
            HAVING COUNT(DISTINCT co.competitor_id) >= %s
            ORDER BY avg_points DESC LIMIT 15''',
        '''            WHERE {LATEST_SNAPSHOT}{neutral_sql}
            GROUP BY co.country
            HAVING COUNT(DISTINCT co.competitor_id) >= %s
            ORDER BY avg_points DESC LIMIT 15''',
    ),
    # 3) "N of M countries" counts
    (
        '''            JOIN Competitors co ON r.competitor_id = co.competitor_id WHERE {LATEST_SNAPSHOT}
        """)''',
        '''            JOIN Competitors co ON r.competitor_id = co.competitor_id WHERE {LATEST_SNAPSHOT}{neutral_sql}
        """)''',
    ),
    (
        '''                WHERE {LATEST_SNAPSHOT}
                GROUP BY co.country HAVING COUNT(DISTINCT co.competitor_id) >= %s''',
        '''                WHERE {LATEST_SNAPSHOT}{neutral_sql}
                GROUP BY co.country HAVING COUNT(DISTINCT co.competitor_id) >= %s''',
    ),
    # 4) total points chart + the grand total used for its shares
    (
        '''            WHERE {LATEST_SNAPSHOT}
            GROUP BY co.country ORDER BY total_points DESC LIMIT 10''',
        '''            WHERE {LATEST_SNAPSHOT}{neutral_sql}
            GROUP BY co.country ORDER BY total_points DESC LIMIT 10''',
    ),
    (
        '''grand_total = run_query(f"SELECT SUM(r.points) AS n FROM Competitor_Rankings r WHERE {LATEST_SNAPSHOT}")''',
        '''grand_total = run_query(f"""
            SELECT SUM(r.points) AS n FROM Competitor_Rankings r
            JOIN Competitors co ON r.competitor_id = co.competitor_id WHERE {LATEST_SNAPSHOT}{neutral_sql}
        """)''',
    ),
    # 5) say so in the insight text
    (
        '''% of all ranking points; "''',
        '''% of all ranking points{neutral_note}; "''',
    ),
]

if not os.path.exists(target):
    sys.exit(f"File not found: {target}\nRun this from the project folder, or pass the path: python patch_exclude_neutral.py path\\to\\streamlit_app.py")

with open(target, "r", encoding="utf-8") as f:
    text = f.read()

if "exclude_neutral" in text:
    sys.exit("Already patched - nothing to do.")

for i, (old, _) in enumerate(EDITS, 1):
    if text.count(old) != 1:
        sys.exit(f"Could not find the exact lines for edit {i} of {len(EDITS)} (the file may have been edited there). "
                 "No changes were made.")

new_text = text
for old, new in EDITS:
    new_text = new_text.replace(old, new)

shutil.copyfile(target, target + ".bak3")
with open(target, "w", encoding="utf-8") as f:
    f.write(new_text)
print(f"Patched OK ({len(EDITS)} edits). Backup saved as {target}.bak3")
