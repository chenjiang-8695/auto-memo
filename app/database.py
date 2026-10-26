"""SQLite 数据层：备忘录的增删改查、到期查询、状态标记。

备忘来源 source 取值：text（手动输入）/ voice（语音识别）/ ocr（OCR 识别）。
提醒时间 remind_at 为本地时间字符串 'YYYY-MM-DD HH:MM:SS'，NULL 表示不提醒。
"""
import os
import sqlite3
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "memos.db")

SOURCE_TEXT = "text"
SOURCE_VOICE = "voice"
SOURCE_OCR = "ocr"
SOURCE_LABELS = {SOURCE_TEXT: "文字", SOURCE_VOICE: "语音", SOURCE_OCR: "OCR"}

TIME_FMT = "%Y-%m-%d %H:%M:%S"
_KEEP = object()  # update_memo 中“保持原值”的哨兵


class Database:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'text',
                    remind_at TEXT,
                    notified INTEGER NOT NULL DEFAULT 0,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _now():
        return datetime.now().strftime(TIME_FMT)

    # ---------- 增 ----------
    def add_memo(self, content, source=SOURCE_TEXT, remind_at=None):
        """新增备忘录，返回新记录 id。remind_at 为字符串或 None。"""
        now = self._now()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO memos (content, source, remind_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (content.strip(), source, remind_at, now, now),
            )
            return cur.lastrowid

    # ---------- 改 ----------
    def update_memo(self, memo_id, content=_KEEP, remind_at=_KEEP, done=_KEEP):
        sets, params = [], []
        if content is not _KEEP:
            sets.append("content=?")
            params.append(content.strip())
        if remind_at is not _KEEP:  # None 表示清除提醒
            sets.append("remind_at=?")
            params.append(remind_at)
            sets.append("notified=0")
        if done is not _KEEP:
            sets.append("done=?")
            params.append(int(done))
        if not sets:
            return
        sets.append("updated_at=?")
        params.append(self._now())
        params.append(memo_id)
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE memos SET {', '.join(sets)} WHERE id=?", params
            )

    def mark_notified(self, memo_id):
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE memos SET notified=1 WHERE id=?", (memo_id,)
            )

    # ---------- 删 ----------
    def delete_memo(self, memo_id):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM memos WHERE id=?", (memo_id,))

    # ---------- 查 ----------
    def get_memo(self, memo_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memos WHERE id=?", (memo_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_memos(self, search="", status="all"):
        """status: all / pending（未完成）/ reminded（有提醒且未完成）/ done"""
        sql = "SELECT * FROM memos"
        conds, params = [], []
        if search:
            conds.append("content LIKE ?")
            params.append(f"%{search}%")
        if status == "pending":
            conds.append("done = 0")
        elif status == "reminded":
            conds.append("done = 0 AND remind_at IS NOT NULL")
        elif status == "done":
            conds.append("done = 1")
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        # 未完成且有提醒的按提醒时间升序排最前，其余按更新时间倒序
        sql += (
            " ORDER BY CASE WHEN done=0 AND remind_at IS NOT NULL THEN 0 ELSE 1 END,"
            " remind_at ASC, updated_at DESC"
        )
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def due_memos(self):
        """到期且尚未提醒、未完成的备忘录。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM memos WHERE remind_at IS NOT NULL"
                " AND notified = 0 AND done = 0 AND remind_at <= ?",
                (self._now(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_pending(self):
        """最近一条未完成备忘（用于悬浮窗展示）。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memos WHERE done = 0"
                " ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def close(self):
        with self._lock:
            self._conn.close()
