"""
概览面板：顶部统计 dashboard
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
)


class StatCard(QFrame):
    """单个统计卡片"""
    
    def __init__(self, title: str, value: str, color: str = "#333", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #888; font-size: 11px; border: none;")
        layout.addWidget(self.title_label)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: bold; border: none;"
        )
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(
                f"color: {color}; font-size: 22px; font-weight: bold; border: none;"
            )


class OverviewPanel(QWidget):
    """顶部概览：总消息 / 客诉 / 紧急数 / 各类别分布"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        self.card_total = StatCard("📊 总消息", "0", "#333")
        self.card_complaint = StatCard("🔥 客诉", "0 (0%)", "#FF5722")
        self.card_urgent = StatCard("🚨 紧急 (≥4)", "0", "#F44336")
        self.card_warning = StatCard("⚠️ 一般 (3)", "0", "#FF9800")
        self.card_tech = StatCard("🛠 技术", "0", "#2196F3")
        self.card_money = StatCard("💰 商业", "0", "#9C27B0")
        
        for card in [
            self.card_total, self.card_complaint, self.card_urgent,
            self.card_warning, self.card_tech, self.card_money,
        ]:
            layout.addWidget(card)
        
        layout.addStretch()
    
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
        money_count = cat_map.get("monetization", 0)
        
        self.card_total.set_value(str(total))
        self.card_complaint.set_value(f"{complaints} ({rate:.0f}%)")
        self.card_urgent.set_value(str(urgent_high), "#F44336")
        self.card_warning.set_value(str(warning), "#FF9800")
        self.card_tech.set_value(str(tech_count), "#2196F3")
        self.card_money.set_value(str(money_count), "#9C27B0")
