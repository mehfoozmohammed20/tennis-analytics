"""Tests for etl.reconcile and etl.load.split_sql_statements (no database needed)."""
from etl.reconcile import raw_vs_transformed, reconcile_with_db, unique_keys
from etl.load import split_sql_statements


def test_raw_vs_transformed_detects_skipped_records():
    raw = {
        "competitions": {"competitions": [{"id": "a"}, {"id": "b"}]},
        "complexes": {"complexes": [{"id": "x", "venues": [{"id": "v1"}, {"id": "v2"}]}]},
        "doubles_rankings": {"rankings": [{"competitor_rankings": [{}, {}, {}]}]},
    }
    transformed = {"competitions": [{"competition_id": "a"}], "complexes": [{}],
                   "venues": [{}, {}], "rankings": [{}, {}, {}]}
    r = raw_vs_transformed(raw, transformed)
    assert r["competitions"]["match"] is False       # one record skipped
    assert r["complexes"]["match"] is True
    assert r["venues"]["match"] is True
    assert r["ranking_rows"]["match"] is True


def test_unique_keys_counts_composite_keys():
    rows = [{"a": 1, "b": 1}, {"a": 1, "b": 1}, {"a": 1, "b": 2}]
    assert unique_keys(rows, ("a", "b")) == 2


class FakeCursor:
    """Returns scripted COUNT(*) results in the order queries are issued."""
    def __init__(self, counts):
        self.counts = list(counts)
        self._last = None

    def execute(self, sql):
        self._last = self.counts.pop(0)

    def fetchone(self):
        return (self._last,)


def test_reconcile_with_db_ok_and_failure():
    transformed = {"categories": [{"category_id": "k1"}, {"category_id": "k1"}]}   # 2 rows, 1 unique
    ok = reconcile_with_db(transformed, FakeCursor([1, 0]))   # categories count, then duplicate-group count
    assert ok["categories"]["unique_rows_this_run"] == 1
    assert ok["categories"]["duplicates_collapsed_by_upsert"] == 1
    assert ok["categories"]["ok"] is True
    assert ok["rankings_duplicate_groups_in_db"]["ok"] is True

    bad = reconcile_with_db(transformed, FakeCursor([0, 3]))  # nothing in DB, 3 duplicate groups
    assert bad["categories"]["ok"] is False
    assert bad["rankings_duplicate_groups_in_db"]["ok"] is False


def test_split_sql_statements_drops_comments_and_splits():
    sql = "-- a comment\nCREATE VIEW a AS SELECT 1;\n\n-- another\nCREATE VIEW b AS SELECT 2;\n"
    stmts = split_sql_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("CREATE VIEW a")
