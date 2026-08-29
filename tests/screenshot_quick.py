"""
截图：快速抓取 UI

场景：
1. 快速抓取空状态
2. 粘链接后实时解析
3. 切换到目标管理模式
"""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.chdir("/tmp")
if Path("/tmp/.env").exists():
    Path("/tmp/.env").unlink()
for k in list(os.environ.keys()):
    if k.startswith("MINIMAX_"):
        del os.environ[k]

sys.path.insert(0, '/workspace/game-ops-monitor')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication.instance() or QApplication([])

from src.gui.main_window import MainWindow

# 截图 1: 空状态（快速抓取模式）
window = MainWindow()
window.resize(1400, 900)
window.show()
app.processEvents()
QTimer.singleShot(200, lambda: None)
app.processEvents()
window.grab().save("/workspace/game-ops-monitor/docs/screenshot_quick_empty.png")
print("✓ 截图 1: 快速抓取空状态")

# 截图 2: 粘链接后
window.source_panel.url_input.setText(
    "https://play.google.com/store/apps/details?id=com.supercell.clashroyale&hl=zh"
)
app.processEvents()
QTimer.singleShot(200, lambda: None)
app.processEvents()
window.grab().save("/workspace/game-ops-monitor/docs/screenshot_quick_parsed.png")
print("✓ 截图 2: 粘链接后实时解析")

# 截图 3: 切到目标管理模式
window.source_panel._switch_mode("target")
app.processEvents()
QTimer.singleShot(200, lambda: None)
app.processEvents()
window.grab().save("/workspace/game-ops-monitor/docs/screenshot_target_mode.png")
print("✓ 截图 3: 目标管理模式")

window.close()
print("\n✅ 截图完成")
