"""
数据源选择面板

两种模式：
1. 快速抓取（推荐）：粘 Google Play 链接 → 自动解析 → 抓取
2. 目标管理（高级）：从 config.yaml 选已配置的目标
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QSpinBox, QFormLayout, QComboBox, QStackedWidget,
    QToolButton, QSizePolicy
)

from ...config import load_config
from ...models import Source
from ...sources import SourceFactory
from ...sources.url_parser import parse_google_play_url, is_valid_package_name

logger = logging.getLogger(__name__)


# 时间范围预设
TIME_RANGES = [
    (1, "最近 1 天"),
    (3, "最近 3 天"),
    (7, "最近 7 天"),
    (14, "最近 14 天"),
    (30, "最近 30 天"),
    (90, "最近 90 天"),
    (None, "不限时间"),
]


class SourcePanel(QWidget):
    """
    数据源 + 目标 + 抓取 控制面板
    """
    
    # 信号：点击"抓取"按钮
    fetch_requested = pyqtSignal(dict)  # payload dict
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sources: dict[Source, object] = {}
        self._build_ui()
        self._load_sources()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # ---- 顶部：快速抓取（最显眼）----
        layout.addWidget(self._build_quick_panel())
        
        # ---- 中部：模式切换 ----
        mode_bar = QHBoxLayout()
        mode_bar.setContentsMargins(8, 0, 8, 0)
        
        self.mode_quick_btn = QToolButton()
        self.mode_quick_btn.setText("⚡ 快速抓取")
        self.mode_quick_btn.setCheckable(True)
        self.mode_quick_btn.setChecked(True)
        self.mode_quick_btn.clicked.connect(lambda: self._switch_mode("quick"))
        
        self.mode_target_btn = QToolButton()
        self.mode_target_btn.setText("📋 目标管理")
        self.mode_target_btn.setCheckable(True)
        self.mode_target_btn.clicked.connect(lambda: self._switch_mode("target"))
        
        mode_bar.addWidget(self.mode_quick_btn)
        mode_bar.addWidget(self.mode_target_btn)
        mode_bar.addStretch()
        
        layout.addLayout(mode_bar)
        
        # ---- 模式面板（堆叠）----
        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_quick_form())      # index 0
        self.mode_stack.addWidget(self._build_target_form())     # index 1
        layout.addWidget(self.mode_stack)
    
    def _build_quick_panel(self) -> QWidget:
        """顶部快速抓取主区（带标题和显眼按钮）"""
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E3F2FD, stop:1 #F3E5F5);
                border: 1px solid #BBDEFB;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("⚡ 快速抓取")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976D2;")
        layout.addWidget(title)
        
        # 链接输入行
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        
        url_label = QLabel("🔗 商店链接:")
        url_label.setStyleSheet("color: #555; font-size: 12px;")
        url_label.setMinimumWidth(80)
        url_row.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "粘 Google Play 链接，如:\n"
            "https://play.google.com/store/apps/details?id=com.xxx"
        )
        self.url_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 2px solid #BBDEFB;
                border-radius: 4px;
                background: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #1976D2;
            }
        """)
        self.url_input.textChanged.connect(self._on_url_changed)
        url_row.addWidget(self.url_input, 1)
        
        # 预览标签
        self.url_preview = QLabel("")
        self.url_preview.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 11px;
                padding: 4px 8px;
                background: rgba(255,255,255,0.5);
                border-radius: 3px;
            }
        """)
        self.url_preview.setWordWrap(True)
        url_row.addWidget(self.url_preview, 1)
        
        layout.addLayout(url_row)
        
        # 参数 + 按钮行
        param_row = QHBoxLayout()
        param_row.setSpacing(12)
        
        # 数量
        param_row.addWidget(QLabel("数量:"))
        self.q_limit = QSpinBox()
        self.q_limit.setRange(1, 1000)
        self.q_limit.setValue(100)
        self.q_limit.setSuffix(" 条")
        self.q_limit.setMinimumWidth(100)
        param_row.addWidget(self.q_limit)
        
        # 时间范围
        param_row.addWidget(QLabel("时间:"))
        self.q_days = QComboBox()
        for days, label in TIME_RANGES:
            self.q_days.addItem(label, days)
        # 默认 7 天
        for i, (days, _) in enumerate(TIME_RANGES):
            if days == 7:
                self.q_days.setCurrentIndex(i)
                break
        param_row.addWidget(self.q_days)
        
        # 语言
        param_row.addWidget(QLabel("语言:"))
        self.q_lang = QComboBox()
        self.q_lang.addItems([
            "auto - 不限",
            "zh - 中文",
            "en - English",
            "ja - 日本語",
            "ko - 한국어",
        ])
        param_row.addWidget(self.q_lang)
        
        # 地区
        param_row.addWidget(QLabel("地区:"))
        self.q_country = QComboBox()
        self.q_country.addItems([
            "🌍 global - 全球（多地区）",
            "cn - 中国",
            "us - 美国",
            "jp - 日本",
            "kr - 韩国",
            "tw - 台湾",
            "gb - 英国",
            "de - 德国",
        ])
        param_row.addWidget(self.q_country)
        
        param_row.addStretch()
        
        # 大按钮
        self.q_fetch_btn = QPushButton("🚀 抓取 + 分类")
        self.q_fetch_btn.setMinimumHeight(40)
        self.q_fetch_btn.setMinimumWidth(160)
        self.q_fetch_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 20px;
            }
            QPushButton:hover { background: #1565C0; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.q_fetch_btn.clicked.connect(self._on_quick_fetch)
        param_row.addWidget(self.q_fetch_btn)
        
        layout.addLayout(param_row)
        
        # 提示
        tip = QLabel(
            "💡 也支持直接输入包名，如 <code>com.supercell.clashroyale</code>"
        )
        tip.setStyleSheet("color: #888; font-size: 11px;")
        tip.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(tip)
        
        return container
    
    def _build_quick_form(self) -> QWidget:
        """快速模式下的下半部分（占位）"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 抓取历史
        self.history_label = QLabel("📜 最近抓取")
        self.history_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.history_label)
        
        self.history_text = QLabel("还没有抓取记录")
        self.history_text.setStyleSheet("color: #999; font-size: 11px; padding: 8px;")
        self.history_text.setWordWrap(True)
        layout.addWidget(self.history_text)
        
        layout.addStretch()
        return w
    
    def _build_target_form(self) -> QWidget:
        """目标管理模式（原有的下拉选）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # ---- 数据源 ----
        source_group = QGroupBox("📡 数据源")
        source_layout = QVBoxLayout(source_group)
        source_layout.setContentsMargins(8, 12, 8, 8)
        
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(140)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_layout.addWidget(self.source_combo)
        
        self.source_status = QLabel("⚪ 未选择")
        self.source_status.setStyleSheet("color: #888; font-size: 11px;")
        source_layout.addWidget(self.source_status)
        
        layout.addWidget(source_group)
        
        # ---- 目标 ----
        target_group = QGroupBox("🎯 目标")
        target_layout = QVBoxLayout(target_group)
        target_layout.setContentsMargins(8, 12, 8, 8)
        
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(180)
        target_layout.addWidget(self.target_combo)
        
        self.target_status = QLabel("")
        self.target_status.setStyleSheet("color: #888; font-size: 11px;")
        target_layout.addWidget(self.target_status)
        
        layout.addWidget(target_group, 1)
        
        # ---- 抓取设置 ----
        fetch_group = QGroupBox("⚙️ 抓取设置")
        fetch_layout = QFormLayout(fetch_group)
        fetch_layout.setContentsMargins(8, 12, 8, 8)
        
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(50)
        self.limit_spin.setSuffix(" 条")
        fetch_layout.addRow("数量:", self.limit_spin)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["zh - 中文", "en - English", "ja - 日本語", "ko - 한국어"])
        fetch_layout.addRow("语言:", self.lang_combo)
        
        self.country_combo = QComboBox()
        self.country_combo.addItems(["cn - 中国", "us - 美国", "jp - 日本", "kr - 韩国", "tw - 台湾"])
        fetch_layout.addRow("地区:", self.country_combo)
        
        layout.addWidget(fetch_group)
        
        # ---- 操作按钮 ----
        action_group = QGroupBox("🚀 操作")
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(8, 12, 8, 8)
        
        self.fetch_btn = QPushButton("🔄 抓取 + 分类")
        self.fetch_btn.setMinimumHeight(36)
        self.fetch_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50; color: white; border: none;
                border-radius: 4px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.fetch_btn.clicked.connect(self._on_fetch_clicked)
        action_layout.addWidget(self.fetch_btn)
        
        self.cancel_btn = QPushButton("⏹ 取消")
        self.cancel_btn.setMinimumHeight(28)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        action_layout.addWidget(self.cancel_btn)
        
        layout.addWidget(action_group)
        
        return container
    
    def _switch_mode(self, mode: str):
        if mode == "quick":
            self.mode_stack.setCurrentIndex(0)
            self.mode_quick_btn.setChecked(True)
            self.mode_target_btn.setChecked(False)
        else:
            self.mode_stack.setCurrentIndex(1)
            self.mode_quick_btn.setChecked(False)
            self.mode_target_btn.setChecked(True)
    
    # ---- URL 解析与预览 ----
    
    def _on_url_changed(self, text: str):
        """URL 输入变化时实时解析"""
        if not text.strip():
            self.url_preview.setText("")
            self.q_fetch_btn.setEnabled(False)
            return
        
        pkg = parse_google_play_url(text)
        if pkg:
            self.url_preview.setText(
                f"✓ 已解析: <b>{pkg}</b>"
            )
            self.url_preview.setStyleSheet("""
                QLabel {
                    color: #2E7D32;
                    font-size: 11px;
                    padding: 4px 8px;
                    background: rgba(76, 175, 80, 0.1);
                    border-radius: 3px;
                }
            """)
            self.q_fetch_btn.setEnabled(True)
        else:
            self.url_preview.setText("⚠️ 无法解析，请检查链接")
            self.url_preview.setStyleSheet("""
                QLabel {
                    color: #C62828;
                    font-size: 11px;
                    padding: 4px 8px;
                    background: rgba(244, 67, 54, 0.1);
                    border-radius: 3px;
                }
            """)
            self.q_fetch_btn.setEnabled(False)
    
    def _on_quick_fetch(self):
        """快速抓取按钮点击"""
        pkg = parse_google_play_url(self.url_input.text())
        if not pkg:
            return
        
        # 解析 country / lang
        country_raw = self.q_country.currentText().split(" - ")[0].strip()
        lang_raw = self.q_lang.currentText().split(" - ")[0].strip()
        
        # 🌍 全球模式
        is_global = country_raw.startswith("🌍") or country_raw == "global"
        
        if is_global:
            payload = {
                "source": "google_play",
                "target_id": pkg,
                "target_name": pkg,
                "limit": self.q_limit.value(),
                "global_mode": True,
                "max_regions": 6,
                "days": self.q_days.currentData(),
                "from_quick_panel": True,
            }
            # 历史记录
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            days_text = f"最近 {self.q_days.currentData()} 天" if self.q_days.currentData() else "不限"
            new_history = f"  • {now} - 🌍 全球抓取 {pkg} ({self.q_limit.value()}条 / {days_text})\n"
            if self.history_text.text() == "还没有抓取记录":
                self.history_text.setText(new_history)
            else:
                self.history_text.setText(new_history + self.history_text.text())
        else:
            payload = {
                "source": "google_play",
                "target_id": pkg,
                "target_name": pkg,
                "limit": self.q_limit.value(),
                "country": country_raw,
                "lang": lang_raw,
                "days": self.q_days.currentData(),
                "from_quick_panel": True,
            }
            # 历史记录
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            days_text = f"最近 {self.q_days.currentData()} 天" if self.q_days.currentData() else "不限"
            new_history = f"  • {now} - 抓取 {pkg} ({self.q_limit.value()}条 / {days_text})\n"
            if self.history_text.text() == "还没有抓取记录":
                self.history_text.setText(new_history)
            else:
                self.history_text.setText(new_history + self.history_text.text())
        
        self.fetch_requested.emit(payload)
        
        # 更新历史
        import datetime as dt
        now = dt.datetime.now().strftime("%H:%M:%S")
        days_text = f"最近 {days} 天" if days else "不限"
        new_history = (
            f"  • {now} - 抓取 {pkg} ({self.q_limit.value()}条 / {days_text})\n"
        )
        if self.history_text.text() == "还没有抓取记录":
            self.history_text.setText(new_history)
        else:
            self.history_text.setText(new_history + self.history_text.text())
    
    # ---- 目标模式（保留原有逻辑）----
    
    def _load_sources(self):
        try:
            config = load_config()
            sources = SourceFactory.create_from_config(config)
            self.sources = sources
            
            self.source_combo.clear()
            if not sources:
                self.source_combo.addItem("（无启用数据源）", None)
                self.source_status.setText("⚠️ 请在 config.yaml 中启用数据源")
                self.fetch_btn.setEnabled(False)
                return
            
            for source_type, source in sources.items():
                targets = source.list_targets()
                self.source_combo.addItem(
                    f"{self._source_icon(source_type)} {source_type.value}",
                    source_type.value,
                )
            
            self.fetch_btn.setEnabled(True)
            self._on_source_changed(0)
        
        except Exception as e:
            logger.exception("加载数据源失败")
            self.source_status.setText(f"❌ 配置错误: {e}")
            self.fetch_btn.setEnabled(False)
    
    def _on_source_changed(self, index: int):
        self.target_combo.clear()
        source_type_value = self.source_combo.currentData()
        if not source_type_value:
            return
        
        source_type = Source(source_type_value)
        source = self.sources.get(source_type)
        if not source:
            return
        
        targets = source.list_targets()
        enabled_targets = [t for t in targets if t.enabled]
        
        if not enabled_targets:
            self.target_combo.addItem("（无可用目标）", None)
            self.target_status.setText("⚠️ 请在 config.yaml 添加目标")
            self.fetch_btn.setEnabled(False)
            return
        
        for t in enabled_targets:
            label = f"{t.name}"
            if t.id != t.name:
                label += f"  ({t.id})"
            self.target_combo.addItem(label, {
                "id": t.id,
                "name": t.name,
                "extra": t.extra,
            })
        
        self.target_combo.setCurrentIndex(0)
        self.source_status.setText(f"✓ {len(enabled_targets)} 个目标")
        self.target_status.setText(f"✓ {enabled_targets[0].id}")
        self.fetch_btn.setEnabled(True)
    
    def _source_icon(self, source_type: Source) -> str:
        icons = {
            Source.GOOGLE_PLAY: "🏪",
            Source.DISCORD: "💬",
            Source.APP_STORE: "🍎",
        }
        return icons.get(source_type, "📡")
    
    def _on_fetch_clicked(self):
        target_data = self.target_combo.currentData()
        if not target_data or not isinstance(target_data, dict):
            return
        
        source_type = self.source_combo.currentData()
        if not source_type:
            return
        
        country_code = self.country_combo.currentText().split(" - ")[0]
        lang_code = self.lang_combo.currentText().split(" - ")[0]
        
        payload = {
            "source": source_type,
            "target_id": target_data["id"],
            "target_name": target_data["name"],
            "limit": self.limit_spin.value(),
            "country": country_code,
            "lang": lang_code,
        }
        self.fetch_requested.emit(payload)
    
    def _on_cancel_clicked(self):
        pass
    
    def set_fetching(self, fetching: bool):
        """设置抓取中状态"""
        self.q_fetch_btn.setEnabled(not fetching and self.url_input.text().strip() != "")
        self.fetch_btn.setEnabled(not fetching)
        self.cancel_btn.setEnabled(fetching)
        self.url_input.setEnabled(not fetching)
        self.source_combo.setEnabled(not fetching)
        self.target_combo.setEnabled(not fetching)
        self.limit_spin.setEnabled(not fetching)
        self.q_limit.setEnabled(not fetching)
        self.q_days.setEnabled(not fetching)
        self.q_lang.setEnabled(not fetching)
        self.q_country.setEnabled(not fetching)
