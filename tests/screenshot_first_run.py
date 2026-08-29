"""
截图：首次启动设置流程

场景：
1. 主窗口刚启动（无 API key）
2. 自动弹出设置对话框
"""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 改到测试目录，确保没 API key
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
from src.gui.settings_dialog import SettingsDialog

# 1. 主窗口启动
window = MainWindow()
window.resize(1400, 900)
window.show()
app.processEvents()

# 截图 1：首次启动主窗口（无 API key）
QTimer.singleShot(100, lambda: None)
app.processEvents()
window.grab().save("/workspace/game-ops-monitor/docs/screenshot_first_run.png")
print("✓ 截图 1：首次启动主窗口")

# 2. 打开设置对话框
dlg = SettingsDialog(window)
dlg.api_key_edit.setText("sk-xxxxxxxxxxxxxx")
dlg.base_url_edit.setText("https://api.minimax.io/v1")
dlg.model_edit.setText("MiniMax-M2.5")
dlg.show()
app.processEvents()
QTimer.singleShot(100, lambda: None)
app.processEvents()
dlg.grab().save("/workspace/game-ops-monitor/docs/screenshot_settings.png")
print("✓ 截图 2：设置对话框")

window.close()
dlg.close()
print("\n✅ 截图保存完成")
