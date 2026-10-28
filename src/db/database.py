import os
import sqlite3
from src.models.reup_item import ReupItem


class ReupDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
        return conn

    def _table(self, page_id: str) -> str:
        return f"id_{page_id.replace('-', '_')}"

    def ensure_table(self, page_id: str) -> None:
        table = self._table(page_id)
        with self._connect() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    url     TEXT PRIMARY KEY,
                    content TEXT,
                    pin     TEXT
                )
            """)

    def get_all(self, page_id: str) -> list[ReupItem]:
        self.ensure_table(page_id)
        table = self._table(page_id)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT url, content, pin FROM {table}").fetchall()
        return [ReupItem(url=r[0], content=r[1], pin=r[2]) for r in rows]

    def get_pending(self, page_id: str) -> list[ReupItem]:
        return [item for item in self.get_all(page_id) if not item.is_uploaded]

    def upsert(self, page_id: str, item: ReupItem) -> None:
        self.ensure_table(page_id)
        table = self._table(page_id)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR IGNORE INTO {table} (url, content, pin) VALUES (?, ?, ?)",
                (item.url, item.content, item.pin),
            )

    def update_pin(self, page_id: str, url: str, pin: str) -> None:
        table = self._table(page_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE {table} SET pin=? WHERE url=?", (pin, url))

    def count_stats(self, page_id: str) -> tuple[int, int, int]:
        all_items = self.get_all(page_id)
        uploaded = [i for i in all_items if i.is_uploaded]
        success = [i for i in uploaded if i.is_success]
        failed = [i for i in uploaded if i.is_fail]
        return len(uploaded), len(success), len(failed)
