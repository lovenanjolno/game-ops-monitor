"""
简洁版：依赖 fetch_worker 内置的 logger
"""
import os
import sys
import logging
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.chdir("/tmp")
if os.path.exists("/tmp/.env"):
    os.remove("/tmp/.env")
for k in list(os.environ.keys()):
    if k.startswith("MINIMAX_"):
        del os.environ[k]

sys.path.insert(0, '/workspace/game-ops-monitor')

# 启用 debug 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from PyQt6.QtWidgets import QApplication

# 杀 QMessageBox
from PyQt6.QtWidgets import QMessageBox
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

app = QApplication.instance() or QApplication([])

from src.gui.main_window import MainWindow

# Patch _on_fetch_error/finished 加日志
window = MainWindow()
window.show()
app.processEvents()

orig_finished = window._on_fetch_finished
orig_error = window._on_fetch_error

def my_finished(s):
    print(f">>> [MAIN] _on_fetch_finished: {s}", flush=True)
    orig_finished(s)
    print(f">>> [MAIN] _on_fetch_finished DONE", flush=True)

def my_error(e):
    print(f">>> [MAIN] _on_fetch_error: {e}", flush=True)
    orig_error(e)
    print(f">>> [MAIN] _on_fetch_error DONE", flush=True)

window._on_fetch_finished = my_finished
window._on_fetch_error = my_error

# 触发抓取
print(">>> 触发抓取", flush=True)
payload = {
    "source": "google_play",
    "target_id": "com.star.union.planetant",
    "target_name": "com.star.union.planetant",
    "limit": 3,
    "country": "us",
    "lang": "en",
    "days": 7,
}
window.start_fetch(payload)
print(">>> start_fetch 返回", flush=True)

# 等待 + processEvents
start = time.time()
while time.time() - start < 90:
    app.processEvents()
    if window._fetch_thread and not window._fetch_thread.isRunning():
        for _ in range(30):
            app.processEvents()
        print(f">>> thread 已退出 @ {time.time()-start:.1f}s", flush=True)
        break
    time.sleep(0.5)
else:
    print(">>> 超时 90s", flush=True)

print()
print("="*60)
print(f"thread.isRunning: {window._fetch_thread.isRunning() if window._fetch_thread else 'None'}")
print(f"状态栏: {window.status_bar.currentMessage()}")
print(f"抓取按钮: {window.source_panel.q_fetch_btn.isEnabled()}")
print(f"历史: {window.source_panel.history_text.text()[:200]}")
print("="*60)
window.close()
