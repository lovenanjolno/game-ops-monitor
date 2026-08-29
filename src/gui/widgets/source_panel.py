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
    QToolButton, QSizePolicy, QScrollArea, QFrame, QListWidget, QListWidgetItem,
    QCheckBox, QTextEdit, QGridLayout
)

from ...config import load_config
from ...models import Source
from ...sources import SourceFactory
from ...sources.url_parser import parse_google_play_url, is_valid_package_name
from ...game_library import GameLibrary, Game

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
    # 信号：模式切换（"quick" / "target"），让主窗口调整下半部分布局
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sources: dict[Source, object] = {}
        self.mode_changed_callback = None  # 兼容旧 API
        self._build_ui()
        self._load_sources()
    
    def _build_ui(self):
        # 整个 panel 加一个"折叠/展开"标题栏
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- 折叠标题栏（始终可见，30px 高）----
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E3F2FD, stop:1 #F3E5F5);
                border-bottom: 1px solid #BBDEFB;
            }
        """)
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 4, 8, 4)
        h.setSpacing(8)

        title_lbl = QLabel("📡 数据源")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #1976D2; "
                                "background: transparent; border: none;")
        h.addWidget(title_lbl)

        h.addStretch()

        self.collapse_btn = QPushButton("▼ 收起")
        self.collapse_btn.setFixedHeight(24)
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid #BBDEFB;
                border-radius: 3px;
                padding: 0 8px;
                color: #1976D2;
                font-size: 11px;
            }
            QPushButton:hover { background: white; }
        """)
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        h.addWidget(self.collapse_btn)

        outer.addWidget(header)

        # ---- 内容容器（可折叠）----
        self.content_container = QWidget()
        layout = QVBoxLayout(self.content_container)
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

        outer.addWidget(self.content_container)
        self._collapsed = False

    def _toggle_collapse(self):
        """折叠/展开 内容区"""
        self._collapsed = not self._collapsed
        self.content_container.setVisible(not self._collapsed)
        self.collapse_btn.setText("▼ 展开" if self._collapsed else "▲ 收起")
        # 折叠后整个 panel 高度由标题栏 30px 决定
        if self._collapsed:
            self.setMaximumHeight(40)
        else:
            self.setMaximumHeight(16777215)  # 取消限制
        # 强制重算布局
        self.parent().updateGeometry() if self.parent() else None
        # 触发上层 layout 重新计算
        top = self
        while top.parent() and top.parent().layout():
            top = top.parent()
            top.layout().invalidate()
            top.layout().activate()
            top.updateGeometry()
    
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
        
        # 链接输入行：链接框占 1 stretch，预览默认隐藏（按内容）
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        url_label = QLabel("🔗 商店链接:")
        url_label.setStyleSheet("color: #555; font-size: 12px;")
        url_label.setMinimumWidth(80)
        url_row.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "粘 Google Play 链接或包名（也支持 PC 平台链接）"
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
        url_row.addWidget(self.url_input, 1)  # 占满剩余空间

        # 预览标签：默认隐藏（用户输入后才显示），按内容大小
        self.url_preview = QLabel("")
        self.url_preview.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                background: rgba(255,255,255,0.7);
                border-radius: 3px;
            }
        """)
        self.url_preview.setWordWrap(True)
        self.url_preview.setVisible(False)  # 默认隐藏
        self.url_preview.setMaximumWidth(240)  # 不超过 240px
        url_row.addWidget(self.url_preview, 0)  # stretch=0，按内容
        
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
        layout.setSpacing(4)

        # 抓取历史（带滚动，避免历史多了把窗口撑高）
        self.history_label = QLabel("📜 最近抓取")
        self.history_label.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.history_label)

        self.history_text = QLabel("还没有抓取记录")
        self.history_text.setStyleSheet(
            "color: #999; font-size: 11px; padding: 8px; "
            "background: #fafafa; border-radius: 4px;"
        )
        self.history_text.setWordWrap(True)
        self.history_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        history_scroll = QScrollArea()
        history_scroll.setWidgetResizable(True)
        history_scroll.setWidget(self.history_text)
        history_scroll.setStyleSheet("""
            QScrollArea {
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
            }
        """)
        history_scroll.setMinimumHeight(40)
        history_scroll.setMaximumHeight(80)
        layout.addWidget(history_scroll)

        layout.addStretch()
        return w
    
    def _build_target_form(self) -> QWidget:
        """游戏库管理面板：左侧列表 + 右侧编辑（2列网格）"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ---- 顶部：操作按钮 ----
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        add_btn = QPushButton("➕ 新增")
        add_btn.clicked.connect(self._on_lib_add)
        top_bar.addWidget(add_btn)
        del_btn = QPushButton("🗑 删除")
        del_btn.setStyleSheet("QPushButton { color: #D32F2F; }")
        del_btn.clicked.connect(self._on_lib_delete)
        top_bar.addWidget(del_btn)
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_lib_save)
        top_bar.addWidget(save_btn)
        top_bar.addStretch()
        self.lib_status_label = QLabel("")
        self.lib_status_label.setStyleSheet("color: #888; font-size: 11px;")
        top_bar.addWidget(self.lib_status_label)
        layout.addLayout(top_bar)

        # ---- 主体：左右分栏 ----
        body = QHBoxLayout()
        body.setSpacing(8)

        # 左侧：游戏列表
        left = QFrame()
        left.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 4, 6, 6)
        left_layout.setSpacing(2)
        list_title = QLabel("📚 游戏库")
        list_title.setStyleSheet(
            "color: #888; font-size: 11px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        left_layout.addWidget(list_title)

        self.lib_list = QListWidget()
        self.lib_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #f0f0f0;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f5f5f5;
            }
            QListWidget::item:selected {
                background: #E3F2FD;
                color: #1976D2;
                border-left: 3px solid #1976D2;
            }
            QListWidget::item:hover { background: #f5f5f5; }
        """)
        self.lib_list.currentItemChanged.connect(self._on_lib_select)
        left_layout.addWidget(self.lib_list)

        body.addWidget(left, 1)

        # 右侧：编辑表单（2 列网格）
        right = QFrame()
        right.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 6, 10, 6)
        right_layout.setSpacing(4)
        edit_title = QLabel("✏️ 编辑")
        edit_title.setStyleSheet(
            "color: #888; font-size: 11px; font-weight: bold; "
            "background: transparent; border: none;"
        )
        right_layout.addWidget(edit_title)

        # 2 列网格：label / value（label 在 col 0/2，value 在 col 1/3）
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        def _add_field(row, col, label, widget):
            l = QLabel(label + ":")
            l.setStyleSheet(
                "color: #555; font-size: 12px; "
                "background: transparent; border: none;"
            )
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            l.setMinimumWidth(48)
            grid.addWidget(l, row, col * 2, 1, 1)
            grid.addWidget(widget, row, col * 2 + 1, 1, 1)

        self.lib_name_edit = QLineEdit()
        self.lib_name_edit.setPlaceholderText("如：部落冲突")
        self.lib_name_edit.setMaximumWidth(280)
        _add_field(0, 0, "名称", self.lib_name_edit)

        self.lib_id_edit = QLineEdit()
        self.lib_id_edit.setPlaceholderText("com.xxx.yyy")
        self.lib_id_edit.setMaximumWidth(280)
        _add_field(0, 1, "包名", self.lib_id_edit)

        self.lib_country_combo = QComboBox()
        self.lib_country_combo.addItems([
            "cn", "us", "jp", "kr", "tw", "hk",
            "gb", "de", "fr", "br", "in", "ru",
        ])
        self.lib_country_combo.setMaximumWidth(120)
        _add_field(1, 0, "地区", self.lib_country_combo)

        self.lib_lang_combo = QComboBox()
        self.lib_lang_combo.addItems(["zh", "en", "ja", "ko"])
        self.lib_lang_combo.setMaximumWidth(120)
        _add_field(1, 1, "语言", self.lib_lang_combo)

        self.lib_limit_spin = QSpinBox()
        self.lib_limit_spin.setRange(1, 500)
        self.lib_limit_spin.setValue(50)
        self.lib_limit_spin.setMaximumWidth(120)
        _add_field(2, 0, "数量", self.lib_limit_spin)

        self.lib_days_spin = QSpinBox()
        self.lib_days_spin.setRange(1, 365)
        self.lib_days_spin.setValue(7)
        self.lib_days_spin.setMaximumWidth(120)
        _add_field(2, 1, "时间", self.lib_days_spin)

        # 备注跨 2 列
        notes_label = QLabel("备注:")
        notes_label.setStyleSheet(
            "color: #555; font-size: 12px; "
            "background: transparent; border: none;"
        )
        notes_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lib_notes_edit = QLineEdit()
        self.lib_notes_edit.setPlaceholderText("可选")
        grid.addWidget(notes_label, 3, 0, 1, 1)
        grid.addWidget(self.lib_notes_edit, 3, 1, 1, 3)

        # 启用 checkbox 跨 2 列
        self.lib_enabled_check = QCheckBox("启用（不勾选则不抓）")
        self.lib_enabled_check.setChecked(True)
        self.lib_enabled_check.setStyleSheet(
            "background: transparent; border: none; padding: 4px;"
        )
        grid.addWidget(self.lib_enabled_check, 4, 0, 1, 4)

        right_layout.addLayout(grid)
        right_layout.addStretch()

        body.addWidget(right, 2)
        layout.addLayout(body, 1)

        # ---- 底部：抓取按钮 ----
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)
        self.fetch_btn = QPushButton("🚀 抓取选中游戏")
        self.fetch_btn.setMinimumHeight(32)
        self.fetch_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50; color: white; border: none;
                border-radius: 4px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #45a049; }
            QPushButton:disabled { background: #cccccc; }
        """)
        self.fetch_btn.clicked.connect(self._on_lib_fetch)
        bottom_bar.addWidget(self.fetch_btn, 2)

        self.cancel_btn = QPushButton("⏹ 取消")
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        bottom_bar.addWidget(self.cancel_btn, 1)
        layout.addLayout(bottom_bar)

        # 初始化
        self._library = GameLibrary("config.yaml")
        self._refresh_lib_list()
        self._set_lib_form_enabled(False)

        return container

    # ---- 游戏库事件处理 ----

    def _refresh_lib_list(self):
        """刷新列表显示"""
        self.lib_list.blockSignals(True)  # 防止 currentItemChanged 触发
        self.lib_list.clear()
        for g in self._library.games:
            item = QListWidgetItem(g.display())
            item.setData(Qt.ItemDataRole.UserRole, g.id)
            self.lib_list.addItem(item)
        self.lib_list.blockSignals(False)
        self.lib_status_label.setText(f"共 {len(self._library.games)} 个游戏")

    def _on_lib_select(self, current, previous):
        """列表选中变化 → 填表单"""
        if current is None:
            self._set_lib_form_enabled(False)
            return
        self._set_lib_form_enabled(True)
        game_id = current.data(Qt.ItemDataRole.UserRole)
        g = self._library.find_by_id(game_id)
        if not g:
            return
        self.lib_name_edit.setText(g.name)
        self.lib_id_edit.setText(g.id)
        self.lib_notes_edit.setText(g.notes)
        # 找到对应的下拉项
        self._set_combo_by_label(self.lib_country_combo, g.country)
        self._set_combo_by_label(self.lib_lang_combo, g.lang)
        self.lib_limit_spin.setValue(g.limit)
        self.lib_days_spin.setValue(g.days)
        self.lib_enabled_check.setChecked(g.enabled)

    def _set_combo_by_label(self, combo, code):
        for i in range(combo.count()):
            if combo.itemText(i).startswith(code + " "):
                combo.setCurrentIndex(i)
                return

    def _set_lib_form_enabled(self, enabled: bool):
        self.lib_name_edit.setEnabled(enabled)
        self.lib_id_edit.setEnabled(enabled)
        self.lib_notes_edit.setEnabled(enabled)
        self.lib_country_combo.setEnabled(enabled)
        self.lib_lang_combo.setEnabled(enabled)
        self.lib_limit_spin.setEnabled(enabled)
        self.lib_days_spin.setEnabled(enabled)
        self.lib_enabled_check.setEnabled(enabled)

    def _on_lib_add(self):
        """新增：清空表单，等用户填完点保存"""
        self.lib_list.clearSelection()
        self._set_lib_form_enabled(True)
        self.lib_name_edit.clear()
        self.lib_id_edit.clear()
        self.lib_notes_edit.clear()
        self.lib_country_combo.setCurrentIndex(0)
        self.lib_lang_combo.setCurrentIndex(0)
        self.lib_limit_spin.setValue(50)
        self.lib_days_spin.setValue(7)
        self.lib_enabled_check.setChecked(True)
        self.lib_name_edit.setFocus()

    def _on_lib_delete(self):
        """删除选中的"""
        current = self.lib_list.currentItem()
        if not current:
            return
        game_id = current.data(Qt.ItemDataRole.UserRole)
        g = self._library.find_by_id(game_id)
        if not g:
            return
        # 简单确认（用 QMessageBox 是 OK 的，因为不在 fetch 流程里）
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认删除",
            f"删除游戏「{g.name}」？\n包名: {g.id}\n\n⚠️ 此操作不可撤销，但不会删除已抓取的数据。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._library.delete(game_id)
            self._library.save()
            self._refresh_lib_list()
            self.status_label_safe("✅ 已删除")

    def _on_lib_save(self):
        """保存表单数据到 library + 写 yaml"""
        name = self.lib_name_edit.text().strip()
        pkg = self.lib_id_edit.text().strip()
        if not pkg:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "包名不能为空", "请填写 Google Play 包名，如 com.supercell.clashroyale")
            return
        if not is_valid_package_name(pkg):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "包名格式错误",
                f"「{pkg}」不是合法的 Android 包名\n格式应为: com.xxx.yyy",
            )
            return

        country = self.lib_country_combo.currentText().split(" - ")[0]
        lang = self.lib_lang_combo.currentText().split(" - ")[0]

        # 是新增还是更新？
        current = self.lib_list.currentItem()
        if current and current.data(Qt.ItemDataRole.UserRole) != pkg:
            # 改了 id
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "包名已变更",
                f"原 id: {current.data(Qt.ItemDataRole.UserRole)}\n"
                f"新 id: {pkg}\n\n"
                f"这会删除旧条目、添加新条目。继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._library.delete(current.data(Qt.ItemDataRole.UserRole))

        new_game = Game(
            id=pkg,
            name=name or pkg,
            country=country,
            lang=lang,
            limit=self.lib_limit_spin.value(),
            days=self.lib_days_spin.value(),
            notes=self.lib_notes_edit.text().strip(),
            enabled=self.lib_enabled_check.isChecked(),
        )

        existing = self._library.find_by_id(pkg)
        if existing:
            # 更新
            self._library.update(new_game)
            self.status_label_safe(f"✅ 已更新 {pkg}")
        else:
            # 新增
            self._library.add(new_game)
            self.status_label_safe(f"✅ 已新增 {pkg}")

        self._library.save()
        self._refresh_lib_list()
        # 选中新加/更新的项
        for i in range(self.lib_list.count()):
            if self.lib_list.item(i).data(Qt.ItemDataRole.UserRole) == pkg:
                self.lib_list.setCurrentRow(i)
                break

    def _on_lib_fetch(self):
        """抓取选中的游戏"""
        current = self.lib_list.currentItem()
        if not current:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "未选择", "请先在左侧列表里选一个游戏")
            return
        game_id = current.data(Qt.ItemDataRole.UserRole)
        g = self._library.find_by_id(game_id)
        if not g or not g.enabled:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "未启用", f"游戏「{g.name if g else game_id}」未启用，请先勾选启用")
            return

        # 复用 fetch_requested 信号
        payload = {
            "source": "google_play",
            "target_id": g.id,
            "target_name": g.name,
            "limit": g.limit,
            "country": g.country,
            "lang": g.lang,
            "days": g.days,
            "global_mode": True,
            "max_regions": 6,
        }
        self.fetch_requested.emit(payload)

    def status_label_safe(self, msg: str):
        """设置 lib 状态栏文字"""
        self.lib_status_label.setText(msg)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.lib_status_label.setText(""))
    
    def _switch_mode(self, mode: str):
        if mode == "quick":
            self.mode_stack.setCurrentIndex(0)
            self.mode_quick_btn.setChecked(True)
            self.mode_target_btn.setChecked(False)
        else:
            self.mode_stack.setCurrentIndex(1)
            self.mode_quick_btn.setChecked(False)
            self.mode_target_btn.setChecked(True)

        # 通知主窗口：调整下半部分（客诉列表 + 详情）的显示
        # 让目标管理模式有更多纵向空间
        self.mode_changed.emit(mode)
        if self.mode_changed_callback:
            self.mode_changed_callback(mode)
    
    # ---- URL 解析与预览 ----
    
    def _on_url_changed(self, text: str):
        """URL 输入变化时实时解析"""
        if not text.strip():
            self.url_preview.setText("")
            self.url_preview.setVisible(False)
            self.q_fetch_btn.setEnabled(False)
            return

        pkg = parse_google_play_url(text)
        if pkg:
            self.url_preview.setText(f"✓ {pkg}")
            self.url_preview.setStyleSheet("""
                QLabel {
                    color: #2E7D32;
                    font-size: 11px;
                    padding: 4px 8px;
                    background: rgba(76, 175, 80, 0.1);
                    border-radius: 3px;
                }
            """)
            self.url_preview.setVisible(True)
            self.q_fetch_btn.setEnabled(True)
        else:
            self.url_preview.setText("⚠️ 无法解析")
            self.url_preview.setStyleSheet("""
                QLabel {
                    color: #C62828;
                    font-size: 12px;
                    padding: 4px 8px;
                    background: rgba(244, 67, 54, 0.1);
                    border-radius: 3px;
                }
            """)
            self.url_preview.setVisible(True)
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
    
    # ---- 数据源加载（只做最小化：保留 self.sources，不再操作旧 UI）----
    
    def _load_sources(self):
        """仅初始化数据源映射，不再操作旧的 source_combo/source_status"""
        try:
            config = load_config()
            self.sources = SourceFactory.create_from_config(config)
            # 启用抓取按钮
            if hasattr(self, "fetch_btn") and self.fetch_btn is not None:
                self.fetch_btn.setEnabled(bool(self.sources))
            if hasattr(self, "q_fetch_btn") and self.q_fetch_btn is not None:
                self.q_fetch_btn.setEnabled(bool(self.sources))
        except Exception as e:
            logger.exception("加载数据源失败")
            self.sources = {}
            self.fetch_btn.setEnabled(False)
    
    def _on_source_changed(self, index: int):
        """旧的目标模式下拉选择事件，已废弃。游戏库有自己的 _on_lib_fetch。"""
        pass

    def _source_icon(self, source_type: Source) -> str:
        icons = {
            Source.GOOGLE_PLAY: "🏪",
            Source.DISCORD: "💬",
            Source.APP_STORE: "🍎",
        }
        return icons.get(source_type, "📡")

    def _on_fetch_clicked(self):
        """旧的目标模式抓取按钮，已废弃。游戏库有自己的 _on_lib_fetch。"""
        pass

    def _on_cancel_clicked(self):
        pass
    
    def set_fetching(self, fetching: bool):
        """设置抓取中状态"""
        self.q_fetch_btn.setEnabled(not fetching and self.url_input.text().strip() != "")
        self.fetch_btn.setEnabled(not fetching)
        self.cancel_btn.setEnabled(fetching)
        self.url_input.setEnabled(not fetching)
        # 旧字段（已废弃）安全兜底
        for attr in ("source_combo", "target_combo", "limit_spin"):
            if hasattr(self, attr):
                getattr(self, attr).setEnabled(not fetching)
        self.q_limit.setEnabled(not fetching)
        self.q_days.setEnabled(not fetching)
        self.q_lang.setEnabled(not fetching)
        self.q_country.setEnabled(not fetching)
