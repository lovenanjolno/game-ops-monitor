"""
截图：修复后状态（抓取失败但不卡死）
"""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.chdir("/tmp")
for k in list(os.environ.keys()):
    if k.startswith("MINIMAX_"):
        del os.environ[k]
if os.path.exists("/tmp/.env"):
    os.remove("/tmp/.env")

sys.path.insert(0, '/workspace/game-ops-monitor')

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from src.gui.main_window import MainWindow

window = MainWindow()
window.resize(1400, 900)
window.show()

# 模拟用户粘链接
window.source_panel.url_input.setText(
    "https://play.google.com/store/apps/details?id=com.star.union.planetant"
)

# 模拟一次失败的抓取（手动设置历史）
window._add_to_history("com.stest1", 50, 12, success=True)
window._add_to_history("com.star.union.planetant", 0, 0, success=False,
                       error="未抓取到任何评论（包名错误、无评论或网络问题）")
window._add_to_history("com.supercell.clashroyale", 100, 38, success=True)
window._add_to_history("com.star.union.planetant", 0, 0, success=False,
                       error="未抓取到任何评论（包名错误、无评论或网络问题）")

window.status_bar.showMessage("❌ 未抓取到任何评论（包名错误、无评论或网络问题）")
app.processEvents()
app.processEvents()

# 截图
import time
time.sleep(0.5)
window.grab().save("/workspace/game-ops-monitor/docs/screenshot_fixed.png")
print("✓ 截图保存")

window.close()
