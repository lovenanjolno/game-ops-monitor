"""
主窗口：Game Ops Monitor

整体布局：
┌─────────────────────────────────────────────────┐
│ Toolbar: [设置] [导出] [统计]      [状态指示]     │
├─────────────────────────────────────────────────┤
│ SourcePanel (数据源 + 目标 + 抓取设置)            │
├─────────────────────────────────────────────────┤
│ OverviewPanel (统计概览)                         │
├──────────────────────────────────┬──────────────┤
│ ComplaintList (左侧列表)         │ DetailPanel │
│                                  │  (右侧详情)  │
│                                  │              │
└──────────────────────────────────┴──────────────┘
│ StatusBar                                        │
└─────────────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QToolBar, QMessageBox, QFileDialog, QApplication
)

from ..config import load_config
from ..storage import SQLiteStore
from .widgets.source_panel import SourcePanel
from .widgets.overview import OverviewPanel
from .widgets.complaint_list import ComplaintListWidget
from .widgets.detail_panel import DetailPanel
from .workers.fetch_worker import FetchWorker
from .settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


# 全局样式
STYLE = """
QMainWindow {
    background: #f5f5f7;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    margin-top: 8px;
    background: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #555;
}

QTableView {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    gridline-color: #f0f0f0;
    selection-background-color: #2196F3;
    selection-color: white;
    alternate-background-color: #fafafa;
}
QTableView::item {
    padding: 6px;
}
QHeaderView::section {
    background: #f0f0f0;
    border: none;
    border-right: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
    padding: 6px;
    font-weight: bold;
    color: #555;
}

QComboBox, QSpinBox, QLineEdit {
    padding: 4px 8px;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    background: white;
}
QComboBox:hover, QSpinBox:hover {
    border-color: #2196F3;
}

QPushButton {
    padding: 6px 16px;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    background: white;
}
QPushButton:hover {
    background: #f0f0f0;
    border-color: #2196F3;
}
QPushButton:pressed {
    background: #d0d0d0;
    border-color: #1976D2;
    padding-top: 7px;
    padding-bottom: 5px;
    padding-left: 17px;
    padding-right: 15px;
}
QPushButton:disabled {
    color: #bbb;
    background: #f8f8f8;
}

QToolButton {
    padding: 4px 10px;
    border: 1px solid transparent;
    border-radius: 4px;
    background: transparent;
}
QToolButton:hover {
    background: #f0f0f0;
    border-color: #d0d0d0;
}
QToolButton:pressed {
    background: #d0d0d0;
}
QToolButton:checked {
    background: #2196F3;
    color: white;
    border-color: #1976D2;
}

QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #d0d0d0;
    border-radius: 3px;
    background: white;
}
QCheckBox::indicator:hover {
    border-color: #2196F3;
}
QCheckBox::indicator:checked {
    background: #2196F3;
    border-color: #1976D2;
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+PHBvbHlsaW5lIHBvaW50cz0iMyw4IDcsMTIgMTMsNCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBmaWxsPSJub25lIi8+PC9zdmc+);
}
QCheckBox::indicator:pressed {
    background: #1976D2;
}

QStatusBar {
    background: white;
    border-top: 1px solid #e0e0e0;
    color: #666;
}
"""


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎮 Game Ops Monitor v0.7.2")
        self.resize(1400, 900)
        # 最小尺寸：保证 1080p 屏幕能完整显示（缩放后 ≈ 900x600）
        self.setMinimumSize(960, 600)
        self.setStyleSheet(STYLE)
        
        # 状态
        self._fetch_thread: Optional[QThread] = None
        self._fetch_worker: Optional[FetchWorker] = None
        
        # 存储
        self._config = load_config()
        self._storage = SQLiteStore(
            self._config.get("storage", {}).get("db_path", "data/monitor.db")
        )

        # 启动时打印关键文件路径（方便确认跑的是不是新代码）
        import os
        for rel in ["src/gui/main_window.py", "src/gui/widgets/detail_panel.py",
                    "src/gui/widgets/complaint_list.py", "src/gui/widgets/overview.py"]:
            fp = os.path.abspath(rel)
            if os.path.exists(fp):
                mtime = os.path.getmtime(fp)
                logger.info(f"[版本检查] {rel}  mtime={mtime:.0f}  size={os.path.getsize(fp)}B")
            else:
                logger.warning(f"[版本检查] {rel} 不存在！")

        # 启动时强制提示版本号（写到状态栏，避免被忽略）
        QTimer.singleShot(1000, lambda: self.status_bar.showMessage(
            f"✅ v0.6.4 已启动 · 当前时间 {datetime.now().strftime('%H:%M:%S')}", 5000
        ))
        
        self._build_ui()
        self._build_menu()
        self._connect_signals()
        
        # 启动时自动刷新
        QTimer.singleShot(500, self.refresh_data)
        
        # 首次启动检测：未配置 API key 则自动打开设置
        QTimer.singleShot(800, self._check_first_run)
    
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 0)
        layout.setSpacing(8)
        
        # 顶部：数据源面板
        self.source_panel = SourcePanel()
        layout.addWidget(self.source_panel)
        
        # 概览
        self.overview = OverviewPanel()
        layout.addWidget(self.overview)
        
        # 主分割：列表 + 详情
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)  # 防止把一侧压成 0

        self.complaint_list = ComplaintListWidget()
        splitter.addWidget(self.complaint_list)

        self.detail_panel = DetailPanel()
        self.detail_panel.setMinimumWidth(420)  # 保证 detail panel 至少 420px 宽
        splitter.addWidget(self.detail_panel)

        # 5:4 比例：list 略大，detail 也不少
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([750, 650])  # 默认 detail 占 650px（更大）

        self.main_splitter = splitter  # 保存引用
        layout.addWidget(splitter, 1)  # stretch
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def _build_menu(self):
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        export_csv_action = QAction("📊 导出 CSV...", self)
        export_csv_action.setShortcut(QKeySequence("Ctrl+E"))
        export_csv_action.triggered.connect(self.export_csv)
        file_menu.addAction(export_csv_action)
        
        export_json_action = QAction("📋 导出 JSON...", self)
        export_json_action.triggered.connect(self.export_json)
        file_menu.addAction(export_json_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("退出", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        refresh_action = QAction("🔄 刷新", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh_data)
        tools_menu.addAction(refresh_action)
        
        settings_action = QAction("⚙️ 设置...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _connect_signals(self):
        self.source_panel.fetch_requested.connect(self.start_fetch)
        self.complaint_list.refresh_requested.connect(self.refresh_data)
        self.complaint_list.row_selected.connect(self.detail_panel.show_detail)
        # 列表操作
        self.complaint_list.delete_requested.connect(self._on_delete_requested)
        self.complaint_list.mark_requested.connect(self._on_mark_requested)
        self.complaint_list.clear_all_requested.connect(self._on_clear_all_requested)
        # 统计卡片点击 → 应用筛选
        self.overview.filter_clicked.connect(self._on_overview_filter)
        # 取消按钮
        self.source_panel.cancel_btn.clicked.connect(self.cancel_fetch)
        # 模式切换：调整下方布局
        self.source_panel.mode_changed.connect(self._on_source_mode_changed)
    
    # ---- 抓取流程 ----
    
    def start_fetch(self, payload: dict):
        """启动抓取"""
        # 检查已有 thread（但允许打断僵尸 thread）
        if self._fetch_thread and self._fetch_thread.isRunning():
            # 如果 30 秒前的僵尸，先清理
            try:
                if self._fetch_started_at and (datetime.now() - self._fetch_started_at).seconds > 30:
                    logger.warning("清理僵尸 thread")
                    self._fetch_thread.quit()
                    self._fetch_thread.wait(1000)
                    self._fetch_thread = None
                else:
                    # 用 status bar 提示，不弹模态框
                    self.status_bar.showMessage("⚠️ 已有抓取任务在进行中，请稍候...")
                    return
            except Exception:
                pass
        
        self._fetch_started_at = datetime.now()
        self.status_bar.showMessage(f"🚀 抓取 {payload['target_id']}...")
        self.source_panel.set_fetching(True)
        
        # 创建 worker
        self._fetch_worker = FetchWorker(
            source_type=payload["source"],
            target_id=payload["target_id"],
            target_name=payload.get("target_name"),
            limit=payload["limit"],
            country=payload.get("country", "cn"),
            lang=payload.get("lang", "zh"),
            days=payload.get("days"),
            global_mode=payload.get("global_mode", False),
            max_regions=payload.get("max_regions", 6),
        )
        
        # 创建线程
        self._fetch_thread = QThread()
        self._fetch_worker.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.finished.connect(self._on_fetch_finished)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.progress.connect(self._on_fetch_progress)
        # finished/error → 停 thread（用 QueuedConnection 保证主线程处理完再 quit）
        self._fetch_worker.finished.connect(
            self._fetch_thread.quit, Qt.ConnectionType.QueuedConnection
        )
        self._fetch_worker.error.connect(
            self._fetch_thread.quit, Qt.ConnectionType.QueuedConnection
        )
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.finished.connect(
            lambda: setattr(self, '_fetch_thread', None)
        )
        
        self._fetch_thread.start()
    
    def cancel_fetch(self):
        if self._fetch_worker:
            self._fetch_worker.cancel()
            self.status_bar.showMessage("⏹ 正在取消...")
    
    def _on_fetch_progress(self, percent: int, message: str):
        self.status_bar.showMessage(f"[{percent}%] {message}")
    
    def _on_fetch_finished(self, stats: dict):
        """抓取完成（非阻塞：用 status bar + 历史记录，不用 QMessageBox）"""
        self.source_panel.set_fetching(False)
        fetched = stats['fetched']
        complaints = stats['complaints']
        failed = stats.get('classify_failed', 0)
        first_err = stats.get('first_failure_reason')

        if failed > 0:
            # 有分类失败，状态栏显示具体原因（截断）
            err_short = (first_err or "未知错误")[:120]
            msg = (f"⚠️ 抓取 {fetched} 条 / 客诉 {complaints} 条 / "
                   f"分类失败 {failed} 条 | {err_short}")
        else:
            msg = (f"✅ 抓取完成: {fetched} 条, "
                   f"客诉 {complaints} 条 "
                   f"({complaints/max(fetched,1)*100:.1f}%) "
                   f"耗时 {stats['fetch_time']:.1f}s")
        self.status_bar.showMessage(msg)

        # 更新最近抓取记录
        self._add_to_history(
            stats.get('target_id', '?'),
            fetched,
            complaints,
            success=True,
            failed=failed,
            error=first_err,
        )

        # 自动刷新列表
        self.refresh_data()
    
    def _on_fetch_error(self, error: str):
        """抓取失败（非阻塞：用 status bar + 历史记录 + 红色提示，不用 QMessageBox）"""
        self.source_panel.set_fetching(False)
        self.status_bar.showMessage(f"❌ {error}")
        
        # 记录到历史
        target_id = self._fetch_worker.target_id if self._fetch_worker else "?"
        self._add_to_history(target_id, 0, 0, success=False, error=error)
    
    def _add_to_history(self, target_id: str, fetched: int, complaints: int,
                       success: bool, error: str = None, failed: int = 0):
        """更新最近抓取记录（避免 QMessageBox 阻塞）"""
        try:
            now = datetime.now().strftime("%H:%M:%S")

            if success:
                if failed > 0:
                    err_short = (error or "未知错误")[:60].replace("\n", " ")
                    line = f"  • {now} ⚠️ {target_id}: {fetched}条 / {failed}分类失败 | {err_short}\n"
                else:
                    line = f"  • {now} ✓ {target_id}: {fetched}条 / {complaints} 客诉\n"
            else:
                err_short = (error or "")[:40]
                line = f"  • {now} ✗ {target_id}: {err_short}\n"

            history_widget = self.source_panel.history_text
            if history_widget.text() == "还没有抓取记录":
                history_widget.setText(line)
            else:
                # 最多保留 10 条
                current = history_widget.text()
                lines = current.strip().split("\n")
                lines = [l for l in lines if l.strip()][-9:]  # 保留最近 9 条
                lines.append(line.strip())
                history_widget.setText("\n".join(lines) + "\n")
        except Exception as e:
            logger.warning(f"更新历史失败: {e}")
    
    # ---- 刷新 / 导出 ----
    
    def refresh_data(self):
        """刷新数据"""
        try:
            filters = self.complaint_list.get_filters()
            rows = self._storage.query_complaints(
                source=filters.get("source"),
                category=filters.get("category"),
                min_urgency=filters.get("min_urgency", 1),
                only_complaints=filters.get("only_complaints", True),
                hide_handled=filters.get("hide_handled", False),
                limit=500,
            )
            self.complaint_list.set_data(rows)

            stats = self._storage.stats()
            self.overview.update_stats(stats)

            filter_desc = "客诉" if filters.get("only_complaints", True) else "全部"
            self.status_bar.showMessage(
                f"✅ 已加载 {len(rows)} 条{filter_desc} / 总 {stats['total_messages']} 条消息"
            )
        except Exception as e:
            logger.exception("刷新失败")
            self.status_bar.showMessage(f"❌ 刷新失败: {e}")

    def _on_overview_filter(self, filter_dict: dict):
        """统计卡片被点击 → 应用对应筛选"""
        # 把 filter 套用到 list（控件同步会触发 refresh）
        self.complaint_list.apply_filter(filter_dict)
        # 状态栏提示
        label = filter_dict.get("label", "筛选")
        self.status_bar.showMessage(f"🔍 已按「{label}」筛选")

    def _on_source_mode_changed(self, mode: str):
        """source panel 模式切换：调整下方 splitter 高度

        切到"目标管理"：折叠客诉列表 + 详情，source panel 占满纵向空间
        切回"快速抓取"：还原列表 + 详情
        """
        layout = self.centralWidget().layout()
        if mode == "target":
            self.complaint_list.setVisible(False)
            self.detail_panel.setVisible(False)
            for i in range(layout.count()):
                item = layout.itemAt(i)
                w = item.widget() if item else None
                if w is self.source_panel:
                    layout.setStretchFactor(w, 10)
                elif w is self.main_splitter:
                    layout.setStretchFactor(w, 0)
        else:
            self.complaint_list.setVisible(True)
            self.detail_panel.setVisible(True)
            for i in range(layout.count()):
                item = layout.itemAt(i)
                w = item.widget() if item else None
                if w is self.source_panel:
                    layout.setStretchFactor(w, 0)
                elif w is self.main_splitter:
                    layout.setStretchFactor(w, 10)

    # ---- 列表操作：标记 / 删除 / 清空 ----

    def _on_delete_requested(self, message_ids: list[int]):
        try:
            n = self._storage.delete_many(message_ids)
            self.complaint_list.remove_rows_by_ids(message_ids)
            self.status_bar.showMessage(f"🗑 已删除 {n} 条")
            logger.info(f"[MainWindow] 删除 {n} 条消息: {message_ids}")
        except Exception as e:
            logger.exception("删除失败")
            self.status_bar.showMessage(f"❌ 删除失败: {e}")

    def _on_mark_requested(self, message_ids: list[int], is_handled: bool):
        try:
            n = self._storage.mark_many_handled(message_ids, is_handled)
            # 局部刷新（避免整表重建闪烁）
            for mid in message_ids:
                self.complaint_list.update_row_handled(mid, is_handled)
            label = "已标记为已处理" if is_handled else "已取消标记"
            self.status_bar.showMessage(f"✅ {n} 条 {label}")
        except Exception as e:
            logger.exception("标记失败")
            self.status_bar.showMessage(f"❌ 标记失败: {e}")

    def _on_clear_all_requested(self):
        try:
            n = self._storage.clear_all()
            self.complaint_list.set_data([])
            self.overview.update_stats({"total_messages": 0, "total_complaints": 0,
                                        "by_category": [], "by_urgency": [], "by_source": []})
            self.status_bar.showMessage(f"🗑 已清空 {n} 条数据")
            logger.warning(f"[MainWindow] 一键清空: 删除 {n} 条")
        except Exception as e:
            logger.exception("清空失败")
            self.status_bar.showMessage(f"❌ 清空失败: {e}")
    
    def export_csv(self):
        """导出 CSV"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", "complaints.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            import csv
            rows = self._storage.query_complaints(only_complaints=True, limit=10000)
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
            self.status_bar.showMessage(f"✓ 已导出 {len(rows)} 条 CSV 到 {path}")
        except Exception as e:
            self.status_bar.showMessage(f"❌ CSV 导出失败: {e}")
    
    def export_json(self):
        """导出 JSON"""
        import json
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 JSON", "complaints.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            rows = self._storage.query_complaints(only_complaints=True, limit=10000)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
            self.status_bar.showMessage(f"✓ 已导出 {len(rows)} 条 JSON 到 {path}")
        except Exception as e:
            self.status_bar.showMessage(f"❌ JSON 导出失败: {e}")
    
    # ---- 工具菜单 ----
    
    def open_settings(self):
        """打开设置对话框（非模态：show() 替代 exec()）"""
        if hasattr(self, '_settings_dialog') and self._settings_dialog and self._settings_dialog.isVisible():
            # 已经有打开的设置窗口，激活它
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        
        self._settings_dialog = SettingsDialog(self)
        # 监听 accepted 信号（保存按钮触发）→ 自动重载配置
        self._settings_dialog.accepted.connect(self._on_settings_saved)
        # 监听 destroyed → 清理引用
        self._settings_dialog.destroyed.connect(lambda: setattr(self, '_settings_dialog', None))
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()
    
    def _on_settings_saved(self):
        """设置保存后的回调"""
        self._config = load_config()
        self.source_panel._load_sources()
        self.status_bar.showMessage("✓ 配置已更新")
    
    def _check_first_run(self):
        """首次启动检测：没配 API key 就引导用户去设置（非模态）"""
        from pathlib import Path
        import os
        
        # 检测 .env 是否有 API key（直接读环境变量或文件）
        api_key = os.getenv("MINIMAX_API_KEY")
        
        if not api_key:
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("MINIMAX_API_KEY="):
                        val = line.split("=", 1)[1].strip()
                        if val and val != "sk-xxxxx":
                            api_key = val
                            break
        
        if not api_key:
            # 首次启动 - 状态栏提示 + 直接打开设置（非模态）
            self.status_bar.showMessage(
                "👋 首次启动：请在打开的设置窗口中填入你的 minimax API Key"
            )
            # 用 show() 替代 exec()，不阻塞主线程
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
        else:
            # ⚠️ 出于安全考虑：不在 UI 显示 key（哪怕前 8 位）。只显示"已配置"
            self.status_bar.showMessage("✅ minimax API Key 已配置")
    
    def show_about(self):
        QMessageBox.about(
            self,
            "关于 Game Ops Monitor",
            "<h2>🎮 Game Ops Monitor v0.1</h2>"
            "<p>游戏运营客诉自动监控系统</p>"
            "<p>基于 PyQt6 + minimax LLM + SQLite</p>"
            "<hr>"
            "<p><b>特性:</b></p>"
            "<ul>"
            "<li>多数据源（Google Play / Discord）</li>"
            "<li>LLM 驱动分类（4 类 + 5 级紧急度）</li>"
            "<li>异步抓取，不阻塞 UI</li>"
            "</ul>"
        )
    
    def closeEvent(self, event):
        """关闭窗口时清理线程（不弹模态框，避免卡死）"""
        if self._fetch_thread and self._fetch_thread.isRunning():
            if self._fetch_worker:
                self._fetch_worker.cancel()
            self._fetch_thread.quit()
            if not self._fetch_thread.wait(2000):
                logger.warning("抓取线程未能在 2s 内退出，强制结束")
                self._fetch_thread.terminate()
                self._fetch_thread.wait(500)
        self._fetch_thread = None
        event.accept()


def run():
    """启动 GUI"""
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("GameOpsMonitor")
    app.setOrganizationName("Mavis")
    
    window = MainWindow()
    window.show()
    
    return app.exec()
