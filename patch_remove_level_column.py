"""
Removes the category_level column from the Competition Explorer TABLE only.
The level chart, the Level filter and the insight text are not touched.

Works whether or not patch_level_display.py was applied before. Your other edits stay untouched.
Usage (from the project folder):   python patch_remove_level_column.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "app", "streamlit_app.py")

CAPTION = '''        st.caption(f"{len(df)} competitions match. Showing the first 1,000 rows in the table.")
'''
NEW_TABLE = '''        show_df(df.head(1000).drop(columns=["category_level"]))
'''

# State A: original file
OLD_A = CAPTION + '''        show_df(df.head(1000))
'''
# State B: after patch_level_display.py
OLD_B = CAPTION + '''        table = df.head(1000).copy()
        # `level` is optional in the API response, so show a missing value as text instead of "None"
        table["category_level"] = table["category_level"].fillna("not provided by API")
        show_df(table)
        st.caption("A level of 'not provided by API' means the SportRadar response has no tournament `level` for that "
                   "competition (the field is optional). It is expected, not a loading error.")
'''

if not os.path.exists(target):
    sys.exit(f"File not found: {target}\nRun this from the project folder, or pass the path: python patch_remove_level_column.py path\\to\\streamlit_app.py")

with open(target, "r", encoding="utf-8") as f:
    text = f.read()

if 'drop(columns=["category_level"])' in text:
    sys.exit("Already removed - nothing to do.")

if text.count(OLD_B) == 1:
    new_text = text.replace(OLD_B, CAPTION + NEW_TABLE)
elif text.count(OLD_A) == 1:
    new_text = text.replace(OLD_A, CAPTION + NEW_TABLE)
else:
    sys.exit("Could not find the exact lines to replace (the file may have been edited there). No changes were made.")

shutil.copyfile(target, target + ".bak2")
with open(target, "w", encoding="utf-8") as f:
    f.write(new_text)
print(f"Done. category_level column removed from the table. Backup saved as {target}.bak2")
