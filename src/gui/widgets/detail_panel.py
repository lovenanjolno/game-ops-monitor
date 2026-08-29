"""
详情面板：选中行后展示完整信息
"""
from __future__ import annotations

import webbrowser
import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QGridLayout
)

logger = logging.getLogger(__name__)


class DetailPanel(QWidget):
    """右侧详情面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: Optional[dict] = None
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # ---- 头部 ----
        self.header_label = QLabel("👈 从左侧选择一条记录")
        self.header_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #555; padding: 8px;"
        )
        layout.addWidget(self.header_label)
        
        # ---- 元数据网格 ----
        meta_frame = QFrame()
        meta_frame.setStyleSheet("""
            QFrame {
                background: #f8f8f8;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        meta_grid = QGridLayout(meta_frame)
        meta_grid.setContentsMargins(8, 8, 8, 8)
        meta_grid.setSpacing(6)
        
        self.meta_labels = {}
        meta_fields = [
            ("id", "ID", 0, 0),
            ("source", "来源", 0, 1),
            ("target", "目标", 0, 2),
            ("category", "类别", 0, 3),
            ("urgency", "紧急度", 1, 0),
            ("confidence", "置信度", 1, 1),
            ("rating", "评分", 1, 2),
            ("author", "作者", 1, 3),
            ("timestamp", "时间", 2, 0, 1, 4),  # 跨 4 列
        ]
        
        for field_data in meta_fields:
            field, label = field_data[0], field_data[1]
            row, col = field_data[2], field_data[3]
            rowspan = field_data[4] if len(field_data) > 4 else 1
            colspan = field_data[5] if len(field_data) > 5 else 1
            
            l = QLabel(f"{label}:")
            l.setStyleSheet("color: #888; font-size: 11px;")
            meta_grid.addWidget(l, row, col * 2, rowspan, 1)
            
            v = QLabel("-")
            v.setStyleSheet("font-weight: bold; color: #333;")
            meta_grid.addWidget(v, row, col * 2 + 1, rowspan, 1)
            self.meta_labels[field] = v
        
        # 时间单独跨 4 列
        if "timestamp" in self.meta_labels:
            t_label = QLabel("时间:")
            t_label.setStyleSheet("color: #888; font-size: 11px;")
            meta_grid.addWidget(t_label, 2, 0)
            # 上面的循环里已经处理过 timestamp，重新规划：时间放第 3 行整行
            # 简化：移除之前添加的，从新添加
            # 实际：上面已经把 timestamp 加到 2,0 位置（label）+ 2,1 (value)
        
        layout.addWidget(meta_frame)
        
        # ---- 摘要 ----
        summary_label = QLabel("📝 摘要:")
        summary_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(summary_label)
        
        self.summary_label = QLabel("-")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1976D2; padding: 4px 0;"
        )
        layout.addWidget(self.summary_label)
        
        # ---- 原文 ----
        content_label = QLabel("💬 原文:")
        content_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(content_label)
        
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.content_text, 1)  # stretch
        
        # ---- LLM 原始响应（可折叠）----
        raw_label = QLabel("🤖 LLM 原始响应（可调试）:")
        raw_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(raw_label)
        
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setMaximumHeight(100)
        self.raw_text.setStyleSheet("""
            QTextEdit {
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: #666;
            }
        """)
        layout.addWidget(self.raw_text)
        
        # ---- 操作按钮 ----
        btn_layout = QHBoxLayout()
        
        self.open_url_btn = QPushButton("🌐 打开原帖")
        self.open_url_btn.setEnabled(False)
        self.open_url_btn.clicked.connect(self._open_url)
        btn_layout.addWidget(self.open_url_btn)
        
        self.copy_btn = QPushButton("📋 复制内容")
        self.copy_btn.clicked.connect(self._copy_content)
        btn_layout.addWidget(self.copy_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def show_detail(self, data: dict):
        """展示一条详情"""
        self._current = data
        
        self.header_label.setText(
            f"📌 客诉 #{data.get('id', '?')}"
        )
        
        # 元数据
        self.meta_labels["id"].setText(str(data.get("id", "-")))
        self.meta_labels["source"].setText(str(data.get("source", "-")))
        self.meta_labels["target"].setText(
            f"{data.get('target_name') or data.get('target_id', '-')}"
        )
        
        # 类别（带 emoji）
        cat = data.get("category")
        cat_display = {
            "tech": "🛠 技术",
            "gameplay": "🎮 玩法",
            "conflict": "⚔ 冲突",
            "monetization": "💰 商业",
        }.get(cat, cat or "-")
        self.meta_labels["category"].setText(cat_display)
        
        # 紧急度
        urgency = data.get("urgency", 0) or 0
        urg_display = {5: "🔴 5 - 立即处理", 4: "🔴 4 - 高", 3: "🟡 3 - 中", 2: "🟢 2 - 低", 1: "⚪ 1 - 观察"}.get(urgency, str(urgency))
        urg_color = {"5": "#F44336", "4": "#F44336", "3": "#FF9800", "2": "#4CAF50", "1": "#9E9E9E"}.get(str(urgency), "#333")
        self.meta_labels["urgency"].setText(urg_display)
        self.meta_labels["urgency"].setStyleSheet(f"font-weight: bold; color: {urg_color};")
        
        # 置信度
        conf = data.get("confidence")
        if conf is not None:
            self.meta_labels["confidence"].setText(f"{conf:.0%}")
        else:
            self.meta_labels["confidence"].setText("-")
        
        # 评分
        rating = data.get("rating")
        self.meta_labels["rating"].setText("⭐" * int(rating) if rating else "-")
        
        self.meta_labels["author"].setText(str(data.get("author", "-")))
        
        # 时间
        ts = data.get("timestamp", "-")
        if isinstance(ts, str) and "T" in ts:
            ts = ts.replace("T", " ")[:19]
        self.meta_labels["timestamp"].setText(str(ts))
        
        # 摘要
        self.summary_label.setText(data.get("summary") or "-")
        
        # 原文
        self.content_text.setPlainText(data.get("content", "-"))
        
        # 原始响应
        self.raw_text.setPlainText(data.get("raw_response") or "（无）")
        
        # 原帖按钮
        url = data.get("url")
        self.open_url_btn.setEnabled(bool(url))
    
    def clear(self):
        self._current = None
        self.header_label.setText("👈 从左侧选择一条记录")
        for label in self.meta_labels.values():
            label.setText("-")
        self.summary_label.setText("-")
        self.content_text.clear()
        self.raw_text.clear()
        self.open_url_btn.setEnabled(False)
    
    def _open_url(self):
        if self._current and self._current.get("url"):
            url = self._current["url"]
            logger.info(f"打开 URL: {url}")
            QDesktopServices.openUrl(QUrl(url))
    
    def _copy_content(self):
        if self._current:
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._current.get("content", ""))
