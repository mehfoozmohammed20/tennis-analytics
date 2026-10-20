"""
One-time patch for app/streamlit_app.py (Competition Explorer table).

What it changes (and nothing else, so your own edits stay untouched):
  - shows a missing tournament level as "not provided by API" instead of "None"
  - adds a short note explaining why
  - adds an expander with a per-category level coverage table, as proof

Usage (from the project folder):   python patch_level_display.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "app", "streamlit_app.py")

OLD = '''        st.caption(f"{len(df)} competitions match. Showing the first 1,000 rows in the table.")
        show_df(df.head(1000))
'''

NEW = '''        st.caption(f"{len(df)} competitions match. Showing the first 1,000 rows in the table.")
        table = df.head(1000).copy()
        # `level` is optional in the API response, so show a missing value as text instead of "None"
        table["category_level"] = table["category_level"].fillna("not provided by API")
        show_df(table)
        st.caption("A level of 'not provided by API' means the SportRadar response has no tournament `level` for that "
                   "competition (the field is optional). It is expected, not a loading error.")
        with st.expander("Which categories have a tournament level?"):
            coverage = run_query("""
                SELECT cat.category_name AS category, COUNT(*) AS competitions,
                       SUM(CASE WHEN c.category_level IS NOT NULL THEN 1 ELSE 0 END) AS with_level
                FROM Competitions c JOIN Categories cat ON c.category_id = cat.category_id
                GROUP BY cat.category_name ORDER BY competitions DESC
            """)
            if not coverage.empty:
                coverage["with_level"] = coverage["with_level"].astype(int)
                coverage["% with level"] = (100 * coverage["with_level"] / coverage["competitions"]).round(1)
                show_df(coverage, hide_index=True)
                st.caption("Measured from your database: a category has levels only where the API provides them.")
'''

if not os.path.exists(target):
    sys.exit(f"File not found: {target}\nRun this from the project folder, or pass the path: python patch_level_display.py path\\to\\streamlit_app.py")

with open(target, "r", encoding="utf-8") as f:
    text = f.read()

if "not provided by API" in text:
    sys.exit("Already patched - nothing to do.")
if text.count(OLD) != 1:
    sys.exit("Could not find the exact lines to replace (the file may have been edited there). "
             "No changes were made.")

shutil.copyfile(target, target + ".bak")
with open(target, "w", encoding="utf-8") as f:
    f.write(text.replace(OLD, NEW))
print(f"Patched OK. Backup saved as {target}.bak")
