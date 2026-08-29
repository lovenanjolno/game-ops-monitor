"""
客诉列表：QTableView + 自定义 Model
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QBrush, QFont, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QComboBox, QLabel, QPushButton, QAbstractItemView, QCheckBox, QMenu,
    QMessageBox, QStyle
)

logger = logging.getLogger(__name__)


# 列定义：(key, 显示名, 默认宽)
COLUMNS = [
    ("handled", "标记", 60),
    ("urgency", "紧急", 60),
    ("timestamp", "时间", 140),
    ("category", "类别", 90),
    ("summary", "摘要", 220),
    ("author", "作者", 110),
    ("rating", "评分", 60),
    ("source", "来源", 70),
    ("product", "产品", 160),
]


class ComplaintModel(QAbstractTableModel):
    """客诉数据 Model"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._headers = [c[1] for c in COLUMNS]

    def set_data(self, data: list[dict]):
        """设置数据"""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return section + 1

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._data):
            return None

        item = self._data[row]
        key = COLUMNS[col][0]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "handled":
                return "✅" if item.get("is_handled") else "⬜"
            return self._format_value(key, item.get(key) or item.get(_fallback_key(key)))

        if role == Qt.ItemDataRole.UserRole:
            # 用于排序：handled 用 0/1，timestamp 用 datetime 对象
            if key == "handled":
                return 1 if item.get("is_handled") else 0
            return item.get(key) or item.get(_fallback_key(key))

        if role == Qt.ItemDataRole.ForegroundRole:
            # 已处理的行用灰色
            if item.get("is_handled"):
                return QBrush(QColor("#9E9E9E"))
            # 紧急度颜色
            if key == "urgency":
                u = item.get("urgency", 0) or 0
                if u >= 4:
                    return QBrush(QColor("#F44336"))
                if u >= 3:
                    return QBrush(QColor("#FF9800"))
                return QBrush(QColor("#4CAF50"))

        if role == Qt.ItemDataRole.FontRole:
            # 已处理行：删除线 + 斜体
            if item.get("is_handled"):
                f = QFont()
                f.setStrikeOut(True)
                f.setItalic(True)
                return f

        if role == Qt.ItemDataRole.ToolTipRole:
            return item.get("content", "")[:300]

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("urgency", "rating", "handled"):
                return Qt.AlignmentFlag.AlignCenter

        return None

    def _format_value(self, key: str, value) -> str:
        if value is None or value == "":
            return "-"
        if key == "urgency":
            icons = {5: "🔴5", 4: "🔴4", 3: "🟡3", 2: "🟢2", 1: "⚪1"}
            return icons.get(int(value), str(value))
        if key == "timestamp":
            ts = value
            if isinstance(ts, str):
                return ts[:19].replace("T", " ")
            return str(ts)[:19]
        if key == "rating":
            score = value
            if score:
                return "⭐" * int(score)
            return "-"
        if key == "category":
            icons = {
                "tech": "🛠 技术",
                "gameplay": "🎮 玩法",
                "conflict": "⚔ 冲突",
                "monetization": "💰 商业",
            }
            return icons.get(value, value or "-")
        return str(value)

    def get_row(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def find_row_by_id(self, message_id: int) -> int:
        """根据 message_id 找行号（-1 = 没找到）"""
        for i, item in enumerate(self._data):
            if item.get("id") == message_id:
                return i
        return -1


def _fallback_key(key: str) -> str:
    """把表格列 key 映射到数据库字段"""
    mapping = {
        "product": "product_name",
    }
    return mapping.get(key, key)


class ComplaintListWidget(QWidget):
    """客诉列表组件"""

    row_selected = pyqtSignal(dict)            # 选中行
    refresh_requested = pyqtSignal()            # 筛选条件变化 / 点刷新
    delete_requested = pyqtSignal(list)         # 删除 [message_id, ...]
    mark_requested = pyqtSignal(list, bool)     # 标记/取消 [message_id, ...], is_handled
    clear_all_requested = pyqtSignal()          # 一键清空

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ---- 筛选栏 ----
        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(8, 4, 8, 4)

        filter_bar.addWidget(QLabel("筛选:"))

        self.filter_source = QComboBox()
        self.filter_source.addItem("全部来源", None)
        self.filter_source.addItem("Google Play", "google_play")
        self.filter_source.addItem("Discord", "discord")
        self.filter_source.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.filter_source)

        self.filter_category = QComboBox()
        self.filter_category.addItem("全部类别", None)
        self.filter_category.addItem("🛠 技术", "tech")
        self.filter_category.addItem("🎮 玩法", "gameplay")
        self.filter_category.addItem("⚔ 冲突", "conflict")
        self.filter_category.addItem("💰 商业", "monetization")
        self.filter_category.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.filter_category)

        self.filter_urgency = QComboBox()
        self.filter_urgency.addItem("全部紧急度", 1)
        self.filter_urgency.addItem("🟡 ≥ 3", 3)
        self.filter_urgency.addItem("🔴 ≥ 4", 4)
        self.filter_urgency.addItem("🚨 = 5", 5)
        self.filter_urgency.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.filter_urgency)

        self.only_complaints_check = QCheckBox("仅客诉")
        self.only_complaints_check.setChecked(True)
        self.only_complaints_check.toggled.connect(self._on_filter_changed)
        filter_bar.addWidget(self.only_complaints_check)

        self.hide_handled_check = QCheckBox("隐藏已处理")
        self.hide_handled_check.setChecked(False)
        self.hide_handled_check.toggled.connect(self._on_filter_changed)
        filter_bar.addWidget(self.hide_handled_check)

        filter_bar.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        filter_bar.addWidget(self.refresh_btn)

        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.setToolTip("清空所有抓取数据（不可恢复）")
        self.clear_btn.setStyleSheet("QPushButton { color: #D32F2F; }")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        filter_bar.addWidget(self.clear_btn)

        layout.addLayout(filter_bar)

        # ---- 列表 ----
        self.model = ComplaintModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        # 列宽
        header = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)
        # 摘要列自适应
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)

        # 默认按紧急度降序
        self.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)  # 紧急度在第 2 列（索引 1）

        # 选中行
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # 提示
        hint = QLabel("💡 右键单条可标记/删除 · 勾选☑︎表示已处理")
        hint.setStyleSheet("color: #888; padding: 2px 8px; font-size: 11px;")
        layout.addWidget(hint)

        layout.addWidget(self.table)

        # ---- 状态 ----
        self.status_label = QLabel("0 条")
        self.status_label.setStyleSheet("color: #888; padding: 4px 8px;")
        layout.addWidget(self.status_label)

    def set_data(self, data: list[dict]):
        self.model.set_data(data)
        # 统计：总 / 已处理 / 未处理
        total = len(data)
        handled = sum(1 for d in data if d.get("is_handled"))
        self.status_label.setText(
            f"共 {total} 条 · 已处理 {handled} · 待处理 {total - handled}"
        )

    def get_selected_ids(self) -> list[int]:
        """获取所有选中行的 message_id（按源 model 顺序）"""
        ids = []
        for proxy_idx in self.table.selectionModel().selectedRows():
            source_row = self.proxy.mapToSource(proxy_idx).row()
            row = self.model.get_row(source_row)
            if row and row.get("id"):
                ids.append(row["id"])
        return ids

    def _on_filter_changed(self):
        self.refresh_requested.emit()

    def _on_selection_changed(self):
        indexes = self.table.selectionModel().selectedRows()
        if indexes:
            source_row = self.proxy.mapToSource(indexes[0]).row()
            row_data = self.model.get_row(source_row)
            if row_data:
                self.row_selected.emit(row_data)

    def _on_context_menu(self, pos: QPoint):
        """右键菜单：标记 / 删除"""
        hit = self.table.indexAt(pos)
        if not hit.isValid():
            return
        # 选中右键那一行（如果还没选）
        if not self.table.selectionModel().isSelected(hit):
            self.table.selectRow(hit.row())

        ids = self.get_selected_ids()
        if not ids:
            return

        menu = QMenu(self)

        n = len(ids)
        n_label = f"{n} 条" if n > 1 else "这条"

        # 当前选中行里"已处理"和"未处理"的数量
        sel_rows = [
            self.model.get_row(self.proxy.mapToSource(p).row())
            for p in self.table.selectionModel().selectedRows()
        ]
        n_handled = sum(1 for r in sel_rows if r and r.get("is_handled"))
        n_unhandled = n - n_handled

        act_mark = QAction(f"✅ 标记{n_label}为已处理", self)
        act_mark.setEnabled(n_unhandled > 0)
        act_mark.triggered.connect(lambda: self.mark_requested.emit(ids, True))
        menu.addAction(act_mark)

        act_unmark = QAction(f"⬜ 取消{n_label}的已处理标记", self)
        act_unmark.setEnabled(n_handled > 0)
        act_unmark.triggered.connect(lambda: self.mark_requested.emit(ids, False))
        menu.addAction(act_unmark)

        menu.addSeparator()

        act_delete = QAction(f"🗑 删除{n_label}", self)
        act_delete.triggered.connect(lambda: self._confirm_delete(ids))
        menu.addAction(act_delete)

        # 切换"标记"列（单击也行：双击 handled 列）
        menu.addSeparator()
        act_toggle = QAction(f"🔁 切换{n_label}的处理状态", self)
        act_toggle.triggered.connect(self._toggle_handled)
        menu.addAction(act_toggle)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _confirm_delete(self, ids: list[int]):
        n = len(ids)
        sample = self.model.get_row(
            self.proxy.mapToSource(self.table.selectionModel().selectedRows()[0]).row()
        )
        sample_author = sample.get("author", "?") if sample else "?"
        sample_summary = (sample.get("summary") or sample.get("content", ""))[:30] if sample else ""

        msg = f"确认删除 {n} 条消息？\n\n"
        if n == 1:
            msg += f"作者: {sample_author}\n摘要: {sample_summary}\n\n"
        msg += "⚠️ 不可恢复。"

        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(ids)

    def _toggle_handled(self):
        """切换选中行的处理状态"""
        sel_rows = self.table.selectionModel().selectedRows()
        if not sel_rows:
            return
        # 全部统一成一个状态：以第一条为准，反向
        first = self.model.get_row(self.proxy.mapToSource(sel_rows[0]).row())
        new_state = not bool(first.get("is_handled")) if first else True
        ids = self.get_selected_ids()
        self.mark_requested.emit(ids, new_state)

    def _on_clear_clicked(self):
        reply = QMessageBox.warning(
            self, "一键清空",
            "⚠️ 将清空所有抓取到的消息、分类结果和抓取记录。\n\n"
            "此操作不可恢复，确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_all_requested.emit()

    def get_filters(self) -> dict:
        return {
            "source": self.filter_source.currentData(),
            "category": self.filter_category.currentData(),
            "min_urgency": self.filter_urgency.currentData() or 1,
            "only_complaints": self.only_complaints_check.isChecked(),
            "hide_handled": self.hide_handled_check.isChecked(),
        }

    # ---- 外部触发：行级局部刷新（标记后无闪烁） ----

    def update_row_handled(self, message_id: int, is_handled: bool):
        """标记后局部更新：避免全表 refresh 闪烁"""
        row = self.model.find_row_by_id(message_id)
        if row < 0:
            return
        self.model._data[row]["is_handled"] = is_handled
        proxy_idx = self.proxy.mapFromSource(self.model.index(row, 0))
        if proxy_idx.isValid():
            self.model.dataChanged.emit(
                self.model.index(row, 0),
                self.model.index(row, self.model.columnCount() - 1),
            )
        # 同步状态栏
        data = self.model._data
        total = len(data)
        handled = sum(1 for d in data if d.get("is_handled"))
        self.status_label.setText(
            f"共 {total} 条 · 已处理 {handled} · 待处理 {total - handled}"
        )

    def remove_rows_by_ids(self, message_ids: list[int]):
        """删除后从 model 里去掉这些行"""
        id_set = set(message_ids)
        # 从后往前删，避免下标错位
        new_data = [d for d in self.model._data if d.get("id") not in id_set]
        self.set_data(new_data)
