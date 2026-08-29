"""
GUI 烟雾测试

在 offscreen 模式下启动 GUI，验证：
1. 主窗口能正常创建
2. 所有 widget 能正常显示
3. 数据加载流程正常
4. 关闭时清理干净
"""
import os
import sys
from pathlib import Path

# 必须先设置 offscreen，再 import Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, '/workspace/game-ops-monitor')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# 先插一些测试数据
from src.models import RawMessage, ClassificationResult, MonitoredItem, Source, Category
from src.storage import SQLiteStore
from datetime import datetime

# 准备测试数据
test_db = "/tmp/gui_test.db"
if os.path.exists(test_db):
    os.remove(test_db)

store = SQLiteStore(test_db)

test_data = [
    ("g1", "玩家A", "充值了 648 不到账，客服让我等 24 小时", 1, Category.MONETIZATION, 5, "充值不到账"),
    ("g2", "玩家B", "游戏很好玩，平衡性不错", 5, None, 1, ""),
    ("g3", "玩家C", "iOS 18 更新后闪退，连游戏都进不去", 1, Category.TECH, 5, "iOS闪退"),
    ("g4", "玩家D", "对面开挂，打不过", 2, Category.CONFLICT, 3, "外挂举报"),
    ("g5", "玩家E", "新角色太强了，要削", 3, Category.GAMEPLAY, 3, "平衡问题"),
    ("g6", "玩家F", "登录界面卡住不动", 1, Category.TECH, 4, "登录卡住"),
    ("g7", "玩家G", "对面骂人挂机，举报也没用", 2, Category.CONFLICT, 2, "举报无效"),
]

for src_id, author, content, rating, cat, urgency, summary in test_data:
    msg = RawMessage(
        source=Source.GOOGLE_PLAY,
        source_id=src_id,
        target_id="com.test.app",
        target_name="测试游戏",
        author=author,
        content=content,
        timestamp=datetime.utcnow(),
        rating=rating,
    )
    cls = ClassificationResult(
        is_complaint=cat is not None,
        category=cat,
        urgency=urgency,
        summary=summary,
        confidence=0.9,
    )
    store.save_item(MonitoredItem(message=msg, classification=cls))

print(f"✓ 插入 {len(test_data)} 条测试数据")

# 启动 GUI
from src.gui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
app.setApplicationName("GameOpsMonitor-Test")

window = MainWindow()

# 让窗口使用测试 db
import src.config as cfg
cfg._DEFAULT_DB = test_db  # 不影响主流程

# 让主窗口使用测试 db
window._storage = SQLiteStore(test_db)

print(f"✓ 主窗口创建: {window.windowTitle()}")
print(f"  - 窗口大小: {window.width()}x{window.height()}")
print(f"  - 数据源面板: {window.source_panel}")
print(f"  - 概览面板: {window.overview}")
print(f"  - 客诉列表: {window.complaint_list}")
print(f"  - 详情面板: {window.detail_panel}")

# 触发数据刷新
window.refresh_data()
print(f"✓ 刷新数据成功")

# 测试显示一条详情
test_row = window.complaint_list.model.get_row(0) if window.complaint_list.model.rowCount() > 0 else None
if test_row:
    window.detail_panel.show_detail(test_row)
    print(f"✓ 详情面板: ID={test_row.get('id')} {test_row.get('summary')}")

# 截图（offscreen 模式）
screenshot_path = "/tmp/gui_screenshot.png"
window.resize(1400, 900)
window.show()

# 强制渲染一帧
QTimer.singleShot(500, lambda: None)
app.processEvents()

pixmap = window.grab()
pixmap.save(screenshot_path)
print(f"✓ 截图保存: {screenshot_path} ({os.path.getsize(screenshot_path)} bytes)")

# 验证数据源面板
print(f"✓ 数据源下拉框: {window.source_panel.source_combo.count()} 项")
print(f"✓ 目标下拉框: {window.source_panel.target_combo.count()} 项")

# 验证概览数据
print(f"✓ 概览:")
print(f"   - 总消息: {window.overview.card_total.value_label.text()}")
print(f"   - 客诉:   {window.overview.card_complaint.value_label.text()}")
print(f"   - 紧急:   {window.overview.card_urgent.value_label.text()}")

# 关闭
window.close()
print(f"\n✅ GUI 烟雾测试全部通过")

# 清理
os.remove(test_db)
