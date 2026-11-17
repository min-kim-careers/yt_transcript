"""SQLite storage. One file: transcripts.db next to this script."""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).with_name("transcripts.db")))
COLUMNS = ["id", "url", "title", "channel", "upload_date", "lang", "status", "full_text", "filtered_text"]


def _run(sql, params=()):
    """Run one query, return rows as dicts."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute(sql, params)]
        con.commit()
        return rows
    finally:
        con.close()


def init():
    _run("""CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY, url TEXT, title TEXT, channel TEXT, upload_date TEXT,
        lang TEXT, status TEXT, full_text TEXT, filtered_text TEXT,
        fetched_at TEXT DEFAULT CURRENT_TIMESTAMP)""")


def known_ids():
    """IDs already handled (ok / no_captions / unavailable) -> never fetched again."""
    return {r["id"] for r in _run("SELECT id FROM videos")}


def save(v):
    placeholders = ",".join("?" * len(COLUMNS))
    _run(f"INSERT OR REPLACE INTO videos ({','.join(COLUMNS)}) VALUES ({placeholders})",
         [v[c] for c in COLUMNS])


def delete(ids):
    """Remove videos. They count as new again, so the next fetch re-downloads them."""
    _run(f"DELETE FROM videos WHERE id IN ({','.join('?' * len(ids))})", ids)


def search(q=""):
    """Video list without the text, for the UI."""
    return _run("""SELECT id, title, channel, upload_date, status, lang, fetched_at FROM videos
                   WHERE title LIKE ? OR channel LIKE ? ORDER BY upload_date DESC""", (f"%{q}%",) * 2)


def get(vid):
    rows = _run("SELECT * FROM videos WHERE id = ?", (vid,))
    return rows[0] if rows else None


def with_text(q=""):
    """Videos with transcripts matching the search, for export."""
    return _run("""SELECT * FROM videos WHERE status = 'ok' AND (title LIKE ? OR channel LIKE ?)
                   ORDER BY upload_date DESC""", (f"%{q}%",) * 2)
