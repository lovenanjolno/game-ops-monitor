"""
SQLite 存储层

表结构：
- messages: 原始消息（去重以 source + source_id 为唯一键）
- classifications: 分类结果（一条消息一条分类）
- fetches: 抓取记录（用于追踪抓取历史）
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import RawMessage, ClassificationResult, MonitoredItem, Source, Category

logger = logging.getLogger(__name__)


class SQLiteStore:
    """SQLite 存储"""
    
    def __init__(self, db_path: str = "data/monitor.db"):
        self.db_path = db_path
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def _init_schema(self):
        """初始化表结构（兼容旧库：缺列则 ALTER TABLE 补上）

        注意：分三步走，避免 executescript 因 index 失败导致整个 script 回滚
        """
        with self._get_conn() as conn:
            # ---- Step 1: 建基础表（旧表已存在则 noop） ----
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_name TEXT,
                    author TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    url TEXT,
                    rating INTEGER,
                    metadata_json TEXT,
                    fetched_at DATETIME NOT NULL,
                    UNIQUE(source, source_id)
                );

                CREATE TABLE IF NOT EXISTS classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    is_complaint BOOLEAN NOT NULL,
                    category TEXT,
                    urgency INTEGER NOT NULL,
                    summary TEXT,
                    confidence REAL,
                    raw_response TEXT,
                    classified_at DATETIME NOT NULL,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                    UNIQUE(message_id)
                );

                CREATE TABLE IF NOT EXISTS fetches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_name TEXT,
                    fetched_count INTEGER NOT NULL,
                    complaint_count INTEGER,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME,
                    status TEXT NOT NULL,
                    error TEXT
                );
            """)

            # ---- Step 2: 兼容旧库 —— 检测列再 ALTER ----
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
            if "is_handled" not in existing_cols:
                conn.execute("ALTER TABLE messages ADD COLUMN is_handled INTEGER NOT NULL DEFAULT 0")
                logger.info("[SQLiteStore] 旧库升级：加 is_handled 列")
            if "product_name" not in existing_cols:
                conn.execute("ALTER TABLE messages ADD COLUMN product_name TEXT NOT NULL DEFAULT ''")
                logger.info("[SQLiteStore] 旧库升级：加 product_name 列")

            # ---- Step 3: 建索引（每个独立 try，缺列则跳过） ----
            index_statements = [
                "CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(source)",
                "CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target_id)",
                "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)",
                "CREATE INDEX IF NOT EXISTS idx_messages_handled ON messages(is_handled)",
                "CREATE INDEX IF NOT EXISTS idx_class_complaint ON classifications(is_complaint)",
                "CREATE INDEX IF NOT EXISTS idx_class_category ON classifications(category)",
                "CREATE INDEX IF NOT EXISTS idx_class_urgency ON classifications(urgency DESC)",
            ]
            for sql in index_statements:
                try:
                    conn.execute(sql)
                except Exception as e:
                    # 旧库缺列时这里会失败，不影响主流程
                    logger.debug(f"[SQLiteStore] index 跳过: {sql[:50]}... ({e})")

        logger.info(f"[SQLiteStore] 初始化数据库: {self.db_path}")
    
    # -------- 写入 --------
    
    def save_item(self, item: MonitoredItem) -> int:
        """
        保存一条完整的"消息+分类"记录

        Returns:
            消息 ID
        """
        # product_name 优先用 metadata 里的（由 GooglePlaySource 在抓取时填入）
        product_name = (item.message.metadata or {}).get("product_name") or item.message.target_name or ""

        with self._get_conn() as conn:
            # 1. 插入消息（冲突时更新）
            cursor = conn.execute(
                """
                INSERT INTO messages (
                    source, source_id, target_id, target_name,
                    author, content, timestamp, url, rating,
                    metadata_json, fetched_at, product_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    content = excluded.content,
                    rating = excluded.rating,
                    metadata_json = excluded.metadata_json,
                    product_name = excluded.product_name
                RETURNING id
                """,
                (
                    item.message.source,
                    item.message.source_id,
                    item.message.target_id,
                    item.message.target_name,
                    item.message.author,
                    item.message.content,
                    item.message.timestamp.isoformat(),
                    item.message.url,
                    item.message.rating,
                    json.dumps(item.message.metadata, ensure_ascii=False),
                    item.fetched_at.isoformat(),
                    product_name,
                ),
            )
            row = cursor.fetchone()
            message_id = row["id"]
            
            # 2. 插入分类
            conn.execute(
                """
                INSERT INTO classifications (
                    message_id, is_complaint, category, urgency,
                    summary, confidence, raw_response, classified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    is_complaint = excluded.is_complaint,
                    category = excluded.category,
                    urgency = excluded.urgency,
                    summary = excluded.summary,
                    confidence = excluded.confidence,
                    raw_response = excluded.raw_response,
                    classified_at = excluded.classified_at
                """,
                (
                    message_id,
                    item.classification.is_complaint,
                    item.classification.category,
                    item.classification.urgency,
                    item.classification.summary,
                    item.classification.confidence,
                    item.classification.raw_response,
                    datetime.utcnow().isoformat(),
                ),
            )
            
            return message_id
    
    def save_batch(self, items: list[MonitoredItem]) -> list[int]:
        """批量保存"""
        ids = []
        for item in items:
            ids.append(self.save_item(item))
        return ids
    
    def log_fetch(
        self,
        source: str,
        target_id: str,
        target_name: Optional[str],
        fetched_count: int,
        complaint_count: Optional[int],
        status: str,
        error: Optional[str] = None,
    ) -> int:
        """记录一次抓取"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO fetches (
                    source, target_id, target_name, fetched_count,
                    complaint_count, started_at, finished_at, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    target_id,
                    target_name,
                    fetched_count,
                    complaint_count,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                    status,
                    error,
                ),
            )
            return cursor.lastrowid
    
    # -------- 查询（GUI 和 CLI 都用） --------
    
    def query_complaints(
        self,
        source: Optional[str] = None,
        target_id: Optional[str] = None,
        category: Optional[str] = None,
        min_urgency: int = 1,
        only_complaints: bool = True,
        hide_handled: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        """
        查询客诉（GUI 列表/CLI show 都用这个）
        """
        sql = """
            SELECT
                m.id, m.source, m.source_id, m.target_id, m.target_name,
                m.author, m.content, m.timestamp, m.url, m.rating,
                m.is_handled, m.product_name,
                c.is_complaint, c.category, c.urgency, c.summary, c.confidence
            FROM messages m
            JOIN classifications c ON m.id = c.message_id
            WHERE 1=1
        """
        params = []

        if only_complaints:
            sql += " AND c.is_complaint = 1"
        if source:
            sql += " AND m.source = ?"
            params.append(source)
        if target_id:
            sql += " AND m.target_id = ?"
            params.append(target_id)
        if category:
            sql += " AND c.category = ?"
            params.append(category)
        if min_urgency > 1:
            sql += " AND c.urgency >= ?"
            params.append(min_urgency)
        if hide_handled:
            sql += " AND m.is_handled = 0"

        sql += " ORDER BY c.urgency DESC, m.timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    
    def stats(self) -> dict:
        """统计信息"""
        with self._get_conn() as conn:
            total_messages = conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0]
            total_complaints = conn.execute(
                "SELECT COUNT(*) FROM classifications WHERE is_complaint = 1"
            ).fetchone()[0]
            
            by_category = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM classifications
                WHERE is_complaint = 1 AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()
            
            by_urgency = conn.execute("""
                SELECT urgency, COUNT(*) as count
                FROM classifications
                WHERE is_complaint = 1
                GROUP BY urgency
                ORDER BY urgency DESC
            """).fetchall()
            
            by_source = conn.execute("""
                SELECT m.source, COUNT(*) as count
                FROM messages m
                JOIN classifications c ON m.id = c.message_id
                WHERE c.is_complaint = 1
                GROUP BY m.source
            """).fetchall()
        
        return {
            "total_messages": total_messages,
            "total_complaints": total_complaints,
            "by_category": [dict(r) for r in by_category],
            "by_urgency": [dict(r) for r in by_urgency],
            "by_source": [dict(r) for r in by_source],
        }

    # -------- 用户操作：标记 / 删除 / 清空 --------

    def mark_handled(self, message_id: int, is_handled: bool) -> bool:
        """标记/取消标记一条消息为'已处理'"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE messages SET is_handled = ? WHERE id = ?",
                (1 if is_handled else 0, message_id),
            )
            return cursor.rowcount > 0

    def mark_many_handled(self, message_ids: list[int], is_handled: bool) -> int:
        """批量标记"""
        if not message_ids:
            return 0
        with self._get_conn() as conn:
            placeholders = ",".join("?" * len(message_ids))
            cursor = conn.execute(
                f"UPDATE messages SET is_handled = ? WHERE id IN ({placeholders})",
                (1 if is_handled else 0, *message_ids),
            )
            return cursor.rowcount

    def delete_message(self, message_id: int) -> bool:
        """删除单条消息（外键级联，classifications 也会被删）"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            return cursor.rowcount > 0

    def delete_many(self, message_ids: list[int]) -> int:
        """批量删除"""
        if not message_ids:
            return 0
        with self._get_conn() as conn:
            placeholders = ",".join("?" * len(message_ids))
            cursor = conn.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                message_ids,
            )
            return cursor.rowcount

    def clear_all(self) -> int:
        """一键清空所有数据（同时清 fetches、classifications、messages）"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM classifications")
            conn.execute("DELETE FROM fetches")
            cursor = conn.execute("DELETE FROM messages")
            # 重建自增 ID
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('messages','classifications','fetches')")
            return cursor.rowcount
