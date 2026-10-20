"""Tests main.main() orchestration with the network and database stubbed out."""
import json
import pytest

import main as pipeline

RAW = {
    "competitions": {"competitions": [
        {"id": "c1", "name": "Wimbledon Men Singles", "parent_id": "p1", "type": "singles", "gender": "men",
         "category": {"id": "k1", "name": "ATP"}, "level": "grand_slam"}]},
    "complexes": {"complexes": [{"id": "x1", "name": "Nacional", "venues": [
        {"id": "v1", "name": "Court 1", "city_name": "Santiago", "country_name": "Chile",
         "country_code": "CHL", "timezone": "America/Santiago"}]}]},
    "doubles_rankings": {"rankings": [{"name": "ATP", "year": 2026, "week": 39, "gender": "men",
        "competitor_rankings": [{"rank": 1, "movement": 0, "points": 100, "competitions_played": 10,
        "competitor": {"id": "a", "name": "Alpha", "country": "Finland", "country_code": "FIN", "abbreviation": "ALP"}}]}]},
}


@pytest.fixture()
def stubbed(monkeypatch, tmp_path):
    calls = {"load": 0, "log": []}
    monkeypatch.setattr(pipeline, "QUALITY_REPORT_PATH", str(tmp_path / "quality_report.json"))
    monkeypatch.setattr(pipeline, "run_extraction", lambda: RAW)
    monkeypatch.setattr(pipeline, "run_load", lambda data: calls.__setitem__("load", calls["load"] + 1))
    monkeypatch.setattr(pipeline, "apply_views", lambda: {"applied": 4, "failed": []})
    monkeypatch.setattr(pipeline, "run_db_reconciliation", lambda t: {"competitions": {"ok": True}})
    monkeypatch.setattr(pipeline, "log_run", lambda status, details: calls["log"].append(status))
    return calls, tmp_path


def test_successful_run_writes_complete_report(stubbed):
    calls, tmp_path = stubbed
    report = pipeline.main()
    assert report["status"] == "SUCCESS"
    assert calls["load"] == 1 and calls["log"] == ["SUCCESS"]
    saved = json.loads((tmp_path / "quality_report.json").read_text())
    for key in ("profile", "raw_vs_transformed", "validation", "views", "db_reconciliation", "loaded_counts"):
        assert key in saved
    assert saved["profile"]["competitions"]["level_present"] == 1
    assert saved["profile"]["competitions"]["parent_id_unresolved"] == 1


def test_critical_validation_blocks_load_and_logs_failure(stubbed, monkeypatch):
    calls, tmp_path = stubbed
    bad = json.loads(json.dumps(RAW))
    bad["doubles_rankings"]["rankings"][0]["competitor_rankings"][0]["points"] = -5   # invalid -> critical
    monkeypatch.setattr(pipeline, "run_extraction", lambda: bad)
    with pytest.raises(pipeline.CriticalValidationError):
        pipeline.main()
    assert calls["load"] == 0                      # nothing was loaded
    assert calls["log"] == ["FAILED"]
    assert json.loads((tmp_path / "quality_report.json").read_text())["status"] == "FAILED"
