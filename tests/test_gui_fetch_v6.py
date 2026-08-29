"""
完整模拟用户操作：粘链接 → 抓取 → 看按钮状态
"""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.chdir("/tmp")
if os.path.exists("/tmp/.env"):
    os.remove("/tmp/.env")
for k in list(os.environ.keys()):
    if k.startswith("MINIMAX_"):
        del os.environ[k]

sys.path.insert(0, '/workspace/game-ops-monitor')

from PyQt6.QtWidgets import QApplication, QMessageBox
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

app = QApplication.instance() or QApplication([])

from src.gui.main_window import MainWindow

# 准备一个 API key 避免卡在 LLM 初始化
os.environ["MINIMAX_API_KEY"] = "sk-test"

window = MainWindow()
window.show()
app.processEvents()

# 模拟用户粘链接
print(">>> 用户粘链接", flush=True)
window.source_panel.url_input.setText(
    "https://play.google.com/store/apps/details?id=com.star.union.planetant"
)
app.processEvents()
print(f"  抓取按钮启用: {window.source_panel.q_fetch_btn.isEnabled()}")
print(f"  预览: {window.source_panel.url_preview.text()}")

# 触发抓取
print(">>> 用户点抓取", flush=True)
window.source_panel.q_fetch_btn.click()
app.processEvents()
print(f"  抓取按钮: {window.source_panel.q_fetch_btn.isEnabled()}")
print(f"  取消按钮: {window.source_panel.cancel_btn.isEnabled()}")

# 等待完成
start = time.time()
while time.time() - start < 90:
    app.processEvents()
    if not window._fetch_thread:
        for _ in range(30):
            app.processEvents()
        break
    time.sleep(0.5)

# 让 _on_fetch_error 跑完
for _ in range(50):
    app.processEvents()
    time.sleep(0.1)

print()
print("="*60)
print(f"thread: {window._fetch_thread}")
print(f"抓取按钮: {window.source_panel.q_fetch_btn.isEnabled()}")
print(f"状态栏: {window.status_bar.currentMessage()}")
print(f"历史:")
for line in window.source_panel.history_text.text().split("\n"):
    if line.strip():
        print(f"  {line}")
print("="*60)

window.close()
print("✅ 测试完成 - 用户可以重新抓取了")
