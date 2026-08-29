"""
概览面板：顶部统计 dashboard

每个卡片都可点击，点击后发出 filter 信号，
由 MainWindow 调用 ComplaintList 应用对应筛选。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
)


# 每个卡片的颜色（保持视觉一致）
CARD_COLORS = {
    "total": "#333",
    "complaint": "#FF5722",
    "urgent": "#F44336",
    "warning": "#FF9800",
    "tech": "#2196F3",
    "gameplay": "#9C27B0",
    "money": "#FFA000",
    "other": "#607D8B",
}


class StatCard(QFrame):
    """单个统计卡片（可点击）"""

    clicked = pyqtSignal(dict)  # 发出 filter 字典

    def __init__(self, title: str, value: str, color: str = "#333", filter_dict: dict = None, parent=None):
        super().__init__(parent)
        self.filter_dict = filter_dict or {}
        self._base_color = color
        self._selected = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "color: #888; font-size: 11px; border: none; background: transparent;"
        )
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; border: none; background: transparent;"
        )
        layout.addWidget(self.value_label)

    def _apply_style(self):
        """基础样式：白底 + 圆角 + 边框

        选中态：保留白底，只加粗边框 + 阴影 + 顶部色条
        （不填充背景，避免数字被遮住）
        """
        if self._selected:
            # 选中：白底 + 2px 主题色边框 + 阴影
            self.setStyleSheet(f"""
                StatCard {{
                    background: white;
                    border: 2px solid {self._base_color};
                    border-radius: 6px;
                    padding: 8px;
                }}
                StatCard QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
            # 阴影效果（PyQt6 QSS 不支持 box-shadow，用 GraphicsEffect 补）
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(12)
            shadow.setColor(Qt.GlobalColor.gray)
            shadow.setOffset(0, 2)
            self.setGraphicsEffect(shadow)
        else:
            # 取消 GraphicsEffect（避免一直带阴影）
            self.setGraphicsEffect(None)
            self.setStyleSheet(f"""
                StatCard {{
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    padding: 8px;
                }}
                StatCard:hover {{
                    background: #fafafa;
                    border: 2px solid {self._base_color};
                }}
            """)

    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self._base_color = color
            self.value_label.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: bold; border: none; background: transparent;"
            )

    def set_selected(self, selected: bool):
        """切换选中状态（用于显示"当前正在按此筛选"）"""
        self._selected = selected
        self._apply_style()
        # 数字始终保持原色（不随选中变白）
        self.value_label.setStyleSheet(
            f"color: {self._base_color}; font-size: 22px; font-weight: bold; "
            f"border: none; background: transparent;"
        )
        # 标题也始终保持灰色
        self.title_label.setStyleSheet(
            "color: #888; font-size: 11px; border: none; background: transparent;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.filter_dict)
            super().mousePressEvent(event)


class OverviewPanel(QWidget):
    """顶部概览：8 个统计卡片，全部可点击"""

    filter_clicked = pyqtSignal(dict)  # 任意卡片点击都发这个

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # ---- 8 个卡片 ----
        # filter_dict 定义点击后如何过滤列表
        self.card_total = StatCard(
            "📊 总消息", "0", CARD_COLORS["total"],
            filter_dict={"only_complaints": False, "category": None, "min_urgency": 1, "label": "全部"},
        )
        self.card_complaint = StatCard(
            "🔥 客诉", "0 (0%)", CARD_COLORS["complaint"],
            filter_dict={"only_complaints": True, "category": None, "min_urgency": 1, "label": "客诉"},
        )
        self.card_urgent = StatCard(
            "🚨 紧急 (≥4)", "0", CARD_COLORS["urgent"],
            filter_dict={"only_complaints": True, "min_urgency": 4, "category": None, "label": "紧急"},
        )
        self.card_warning = StatCard(
            "⚠️ 一般 (3)", "0", CARD_COLORS["warning"],
            filter_dict={"only_complaints": True, "min_urgency": 3, "category": None, "label": "一般", "max_urgency": 3},
        )
        self.card_tech = StatCard(
            "🛠 技术", "0", CARD_COLORS["tech"],
            filter_dict={"only_complaints": True, "category": "tech", "min_urgency": 1, "label": "技术"},
        )
        self.card_gameplay = StatCard(
            "🎮 玩法", "0", CARD_COLORS["gameplay"],
            filter_dict={"only_complaints": True, "category": "gameplay", "min_urgency": 1, "label": "玩法"},
        )
        self.card_money = StatCard(
            "💰 商业", "0", CARD_COLORS["money"],
            filter_dict={"only_complaints": True, "category": "monetization", "min_urgency": 1, "label": "商业"},
        )
        self.card_other = StatCard(
            "📦 其他", "0", CARD_COLORS["other"],
            filter_dict={"only_complaints": True, "category": "other", "min_urgency": 1, "label": "其他"},
        )

        self.cards = [
            self.card_total, self.card_complaint, self.card_urgent, self.card_warning,
            self.card_tech, self.card_gameplay, self.card_money, self.card_other,
        ]
        for card in self.cards:
            card.clicked.connect(self._on_card_clicked)
            layout.addWidget(card)

        layout.addStretch()

    def _on_card_clicked(self, filter_dict: dict):
        # 切换选中状态
        for card in self.cards:
            card.set_selected(card.filter_dict == filter_dict)
        self.filter_clicked.emit(filter_dict)

    def reset_selection(self):
        """清掉所有卡片的选中（用于自定义筛选时）"""
        for card in self.cards:
            card.set_selected(False)

    def update_stats(self, stats: dict):
        """刷新数据"""
        total = stats.get("total_messages", 0)
        complaints = stats.get("total_complaints", 0)
        rate = (complaints / total * 100) if total > 0 else 0

        # 紧急度分布
        urg_map = {r["urgency"]: r["count"] for r in stats.get("by_urgency", [])}
        urgent_high = urg_map.get(5, 0) + urg_map.get(4, 0)
        warning = urg_map.get(3, 0)

        # 类别分布
        cat_map = {r["category"]: r["count"] for r in stats.get("by_category", [])}
        tech_count = cat_map.get("tech", 0)
        gameplay_count = cat_map.get("gameplay", 0)
        money_count = cat_map.get("monetization", 0)
        other_count = cat_map.get("other", 0)

        self.card_total.set_value(str(total), CARD_COLORS["total"])
        self.card_complaint.set_value(f"{complaints} ({rate:.0f}%)", CARD_COLORS["complaint"])
        self.card_urgent.set_value(str(urgent_high), CARD_COLORS["urgent"])
        self.card_warning.set_value(str(warning), CARD_COLORS["warning"])
        self.card_tech.set_value(str(tech_count), CARD_COLORS["tech"])
        self.card_gameplay.set_value(str(gameplay_count), CARD_COLORS["gameplay"])
        self.card_money.set_value(str(money_count), CARD_COLORS["money"])
        self.card_other.set_value(str(other_count), CARD_COLORS["other"])
