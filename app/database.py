"""SQLite 数据访问层。

设计要点：
- 计时采用**绝对时间戳**（tbl_reminder_templates.next_due_at），而不是剩余秒数，
  这样软件关闭/重启后仍能按真实时间正确判断是否到点。
- 所有连接使用上下文管理器，确保异常时也能正确提交/回滚并关闭。
- 完成记录保存提醒内容的**快照**，模板被修改/删除不影响历史可追溯性。
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

# ISO 时间格式（精确到秒），用于绝对时间戳的存取
DT_FMT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    """返回当前时间的标准字符串。"""
    return datetime.now().strftime(DT_FMT)


def parse_dt(s: str) -> datetime:
    """把数据库里的时间字符串解析为 datetime。"""
    return datetime.strptime(s, DT_FMT)


class Database:
    """封装 SQLite 的全部读写操作。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # 确保数据库所在目录存在
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        """提供带事务的连接上下文：正常提交，异常回滚，最终关闭。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """首次运行时建表（幂等）。"""
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tbl_reminder_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name   TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL DEFAULT 30,
                    is_active       INTEGER NOT NULL DEFAULT 1,
                    sort_order      INTEGER NOT NULL DEFAULT 0,
                    next_due_at     TEXT,                 -- 下次应提醒的绝对时间（NULL=未排程）
                    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );

                CREATE TABLE IF NOT EXISTS tbl_completion_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_name    TEXT NOT NULL,
                    template_id      INTEGER,
                    template_name    TEXT,               -- 模板名快照
                    reminder_content TEXT,               -- 提醒内容快照
                    reminded_at      TEXT,               -- 提醒弹出时间
                    completed_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    delay_count      INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (template_id)
                        REFERENCES tbl_reminder_templates(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS tbl_user_settings (
                    key        TEXT PRIMARY KEY,
                    value      TEXT,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );
                """
            )

    # ---------- 模板 CRUD ----------

    def list_templates(self, only_active: bool = False):
        """返回模板列表（按 sort_order, id 排序）。"""
        sql = "SELECT * FROM tbl_reminder_templates"
        if only_active:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY sort_order, id"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def get_template(self, template_id: int):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tbl_reminder_templates WHERE id = ?", (template_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_template(self, name: str, content: str, interval_minutes: int,
                     is_active: int = 1, sort_order: int = 0) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO tbl_reminder_templates
                   (template_name, content, interval_minutes, is_active, sort_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, content, interval_minutes, is_active, sort_order),
            )
            return cur.lastrowid

    def update_template(self, template_id: int, name: str, content: str,
                        interval_minutes: int, is_active: int):
        with self._conn() as conn:
            conn.execute(
                """UPDATE tbl_reminder_templates
                   SET template_name=?, content=?, interval_minutes=?, is_active=?
                   WHERE id=?""",
                (name, content, interval_minutes, is_active, template_id),
            )

    def set_template_active(self, template_id: int, is_active: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE tbl_reminder_templates SET is_active=? WHERE id=?",
                (is_active, template_id),
            )

    def delete_template(self, template_id: int):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM tbl_reminder_templates WHERE id=?", (template_id,)
            )

    # ---------- 计时（绝对时间戳） ----------

    def set_next_due(self, template_id: int, due_dt: datetime):
        """设置某模板的下次提醒绝对时间。"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE tbl_reminder_templates SET next_due_at=? WHERE id=?",
                (due_dt.strftime(DT_FMT), template_id),
            )

    def schedule_from_now(self, template_id: int, interval_minutes: int):
        """以当前时间为基准重排某模板：next_due_at = now + interval。"""
        self.set_next_due(template_id, datetime.now() + timedelta(minutes=interval_minutes))

    def ensure_scheduled(self):
        """为所有启用但未排程（next_due_at 为空）的模板补排程。

        在程序启动时调用：新启用的模板从现在开始计时。
        """
        for tpl in self.list_templates(only_active=True):
            if not tpl["next_due_at"]:
                self.schedule_from_now(tpl["id"], tpl["interval_minutes"])

    # ---------- 完成记录 ----------

    def add_completion(self, operator_name: str, template_id, template_name: str,
                       reminder_content: str, reminded_at: str, delay_count: int):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO tbl_completion_records
                   (operator_name, template_id, template_name, reminder_content,
                    reminded_at, completed_at, delay_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (operator_name, template_id, template_name, reminder_content,
                 reminded_at, now_str(), delay_count),
            )

    def list_completions(self, operator_name: str = None,
                         date_from: str = None, date_to: str = None):
        """查询完成记录，支持按姓名和日期范围过滤。"""
        sql = "SELECT * FROM tbl_completion_records WHERE 1=1"
        params = []
        if operator_name:
            sql += " AND operator_name = ?"
            params.append(operator_name)
        if date_from:
            sql += " AND completed_at >= ?"
            params.append(date_from + " 00:00:00")
        if date_to:
            sql += " AND completed_at <= ?"
            params.append(date_to + " 23:59:59")
        sql += " ORDER BY completed_at DESC"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def distinct_operators(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT operator_name FROM tbl_completion_records "
                "WHERE operator_name <> '' ORDER BY operator_name"
            ).fetchall()
            return [r["operator_name"] for r in rows]

    def clear_completions(self):
        with self._conn() as conn:
            conn.execute("DELETE FROM tbl_completion_records")

    # ---------- 用户设置（KV） ----------

    def get_setting(self, key: str, default=None):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM tbl_user_settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO tbl_user_settings (key, value, updated_at)
                   VALUES (?, ?, datetime('now','localtime'))
                   ON CONFLICT(key) DO UPDATE SET
                       value=excluded.value, updated_at=excluded.updated_at""",
                (key, value),
            )
