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
    QPushButton, QFrame, QGridLayout, QSplitter, QScrollArea
)

logger = logging.getLogger(__name__)


class DetailPanel(QWidget):
    """右侧详情面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: Optional[dict] = None
        self._build_ui()
    
    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(8)

        # ---- 头部 ----
        self.header_label = QLabel("👈 从左侧选择一条记录")
        self.header_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #555; padding: 8px;"
        )
        outer_layout.addWidget(self.header_label)

        # ---- 上下 splitter（元数据 / 摘要+原文+LLM+按钮）----
        # 用 12px 宽的把手 + 蓝色 hover 提示，让用户知道这里可以拖
        vsplitter = QSplitter(Qt.Orientation.Vertical)
        vsplitter.setHandleWidth(12)
        vsplitter.setChildrenCollapsible(False)
        vsplitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background: #e8e8e8;
                border-top: 1px solid #d0d0d0;
                border-bottom: 1px solid #d0d0d0;
                image: none;
            }
            QSplitter::handle:vertical:hover {
                background: #2196F3;
                border-top: 1px solid #1976D2;
                border-bottom: 1px solid #1976D2;
            }
            QSplitter::handle:vertical:pressed {
                background: #1976D2;
            }
        """)

        # ---- 上：元数据（独立可滚，QScrollArea 包裹）----
        meta_container = QWidget()
        meta_outer = QVBoxLayout(meta_container)
        meta_outer.setContentsMargins(0, 0, 0, 0)
        meta_outer.setSpacing(4)

        meta_title = QLabel("📋 元数据")
        meta_title.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        meta_outer.addWidget(meta_title)

        # ---- 元数据（2 列网格布局，9 个字段只占 5 行，行高 34px） ----
        meta_frame = QFrame()
        meta_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        grid = QGridLayout(meta_frame)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        meta_fields = [
            ("id",         "ID",     0, 0, 1),
            ("source",     "来源",   0, 2, 1),
            ("target",     "目标",   1, 0, 1),
            ("category",   "类别",   1, 2, 1),
            ("urgency",    "紧急度", 2, 0, 1),
            ("confidence", "置信度", 2, 2, 1),
            ("rating",     "评分",   3, 0, 1),
            ("author",     "作者",   3, 2, 1),
            ("timestamp",  "时间",   4, 0, 3),
        ]

        self.meta_labels = {}
        for field, label, row, col, colspan in meta_fields:
            l = QLabel(f"{label}:")
            l.setStyleSheet(
                "color: #555; font-size: 13px; font-weight: 500; "
                "background: transparent; border: none;"
            )
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            l.setMinimumWidth(64)

            v = QLabel("-")
            v.setStyleSheet(
                "font-weight: bold; color: #111; font-size: 14px; "
                "background: transparent; border: none;"
            )
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.setWordWrap(True)
            v.setMinimumHeight(28)

            if colspan == 3 and field == "timestamp":
                grid.addWidget(l, row, col, 1, 2)
                grid.addWidget(v, row, col + 2, 1, 1)
            else:
                grid.addWidget(l, row, col, 1, 1)
                grid.addWidget(v, row, col + 1, 1, 1)

            self.meta_labels[field] = v

        # 用 QScrollArea 包裹：元数据多了内部可滚
        scroll = QScrollArea()
        scroll.setWidget(meta_frame)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #c0c0c0; border-radius: 4px; }
        """)
        meta_outer.addWidget(scroll, 1)

        vsplitter.addWidget(meta_container)

        # ---- 下：摘要 + 原文 + LLM + 按钮（一个独立 panel）----
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)

        # 摘要
        summary_label = QLabel("📝 摘要:")
        summary_label.setStyleSheet("color: #888; font-size: 11px;")
        bottom_layout.addWidget(summary_label)

        self.summary_label = QLabel("-")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1976D2; padding: 4px 0;"
        )
        bottom_layout.addWidget(self.summary_label)

        # 原文
        content_label = QLabel("💬 原文:")
        content_label.setStyleSheet("color: #888; font-size: 11px;")
        bottom_layout.addWidget(content_label)

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
        bottom_layout.addWidget(self.content_text, 1)  # stretch，吃剩余空间

        # LLM 原始响应（可折叠）
        raw_label = QLabel("🤖 LLM 原始响应（可调试）:")
        raw_label.setStyleSheet("color: #888; font-size: 11px;")
        bottom_layout.addWidget(raw_label)

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setMaximumHeight(120)
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
        bottom_layout.addWidget(self.raw_text)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.open_url_btn = QPushButton("🌐 打开原帖")
        self.open_url_btn.setEnabled(False)
        self.open_url_btn.clicked.connect(self._open_url)
        btn_layout.addWidget(self.open_url_btn)

        self.copy_btn = QPushButton("📋 复制内容")
        self.copy_btn.clicked.connect(self._copy_content)
        btn_layout.addWidget(self.copy_btn)

        btn_layout.addStretch()
        bottom_layout.addLayout(btn_layout)

        vsplitter.addWidget(bottom_container)

        # 默认比例：元数据区 40%，下半部分 60%
        vsplitter.setStretchFactor(0, 4)
        vsplitter.setStretchFactor(1, 6)
        vsplitter.setSizes([280, 420])

        outer_layout.addWidget(vsplitter, 1)

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
            "other": "📦 其他",
        }.get(cat, cat or "-")
        self.meta_labels["category"].setText(cat_display)

        # 紧急度
        urgency = data.get("urgency", 0) or 0
        urg_display = {5: "🔴 5 - 立即处理", 4: "🔴 4 - 高", 3: "🟡 3 - 中", 2: "🟢 2 - 低", 1: "⚪ 1 - 观察"}.get(urgency, str(urgency))
        urg_color = {"5": "#F44336", "4": "#F44336", "3": "#FF9800", "2": "#4CAF50", "1": "#9E9E9E"}.get(str(urgency), "#333")
        self.meta_labels["urgency"].setText(urg_display)
        self.meta_labels["urgency"].setStyleSheet(f"font-weight: bold; color: {urg_color}; font-size: 12px;")
        
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
