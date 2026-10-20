"""The dashboard path (database.connection) must not require the SportRadar API key."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code: str, tmp_cwd) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPORTRADAR_", "DB_"))}
    env["PYTHONPATH"] = ROOT
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(tmp_cwd))


def test_database_connection_imports_without_api_key(tmp_path):
    if os.path.exists(os.path.join(ROOT, ".env")):
        return  # a real .env would be loaded; nothing to prove
    r = _run("import database.connection as c; print(c.DB_CONFIG['database'])", tmp_path)
    assert r.returncode == 0, r.stderr
    assert "tennis_analytics" in r.stdout


def test_api_config_still_demands_key_and_names_the_folder(tmp_path):
    if os.path.exists(os.path.join(ROOT, ".env")):
        return
    r = _run("import api.config", tmp_path)
    assert r.returncode != 0
    assert "SPORTRADAR_API_KEY not found" in r.stderr and ".env" in r.stderr
