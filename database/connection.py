"""
Database connections. Reads settings from .env in the project root.

Two backends, same SQL for the dashboard:
  mysql   the live database. Used when a DB_PASSWORD is configured (your own machine).
  sqlite  a saved snapshot file (data/tennis.db). Used for hosting, so no database server is needed.

Which one is used:
  1. DB_BACKEND=mysql or DB_BACKEND=sqlite in .env / environment, if set
  2. otherwise sqlite when there is NO DB_PASSWORD and the snapshot file exists
  3. otherwise mysql

The ETL pipeline (main.py) always needs MySQL. The snapshot is created from MySQL by
`python database/export_to_sqlite.py`.
"""
import datetime
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root no matter where the app is started from.
# The dashboard only needs the database settings, not the SportRadar API key.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logger = logging.getLogger(__name__)


def mysql_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "3306"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "tennis_analytics"),
    }


DB_CONFIG = mysql_config()


def sqlite_path() -> str:
    path = os.getenv("SQLITE_PATH") or os.path.join("data", "tennis.db")
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def backend_name() -> str:
    """'mysql' or 'sqlite' (see the rules at the top of this file). Read at call time, so tests can change it."""
    explicit = os.getenv("DB_BACKEND", "").strip().lower()
    if explicit in ("mysql", "sqlite"):
        return explicit
    if not os.getenv("DB_PASSWORD") and os.path.exists(sqlite_path()):
        return "sqlite"
    return "mysql"


def backend_label() -> str:
    """Short text for the dashboard sidebar, so viewers know whether the data is live or a snapshot."""
    if backend_name() == "sqlite":
        try:
            saved = datetime.datetime.fromtimestamp(os.path.getmtime(sqlite_path())).strftime("%d %b %Y")
            return f"Data source: saved snapshot ({saved})"
        except OSError:
            return "Data source: saved snapshot"
    return "Data source: MySQL (live)"


class _TranslatingCursor(sqlite3.Cursor):
    """Lets the dashboard keep its MySQL-style %s placeholders when running on SQLite."""

    def execute(self, sql, parameters=()):
        return super().execute(sql.replace("%s", "?"), parameters)

    def executemany(self, sql, seq_of_parameters):
        return super().executemany(sql.replace("%s", "?"), seq_of_parameters)


class _TranslatingConnection(sqlite3.Connection):
    def cursor(self, factory=None):
        return super().cursor(factory or _TranslatingCursor)

    def execute(self, sql, parameters=()):
        return super().execute(sql.replace("%s", "?"), parameters)


def get_sqlite_connection():
    """Read-only connection to the snapshot file."""
    path = sqlite_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Snapshot file not found: {path}. Create it with `python database/export_to_sqlite.py`."
        )
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True, factory=_TranslatingConnection)


def get_mysql_connection():
    import mysql.connector  # imported here so the hosted (SQLite) app does not need the MySQL driver at runtime
    from mysql.connector import Error as MySQLError

    try:
        return mysql.connector.connect(**mysql_config())
    except MySQLError as e:
        logger.error(f"Database connection failed: {e}")
        raise


def get_connection():
    """Connection for the active backend (see the rules at the top of this file)."""
    return get_sqlite_connection() if backend_name() == "sqlite" else get_mysql_connection()
