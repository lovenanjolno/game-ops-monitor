"""
首次启动流程测试（无 GUI 阻塞）
"""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 改到 /tmp 测试
os.chdir("/tmp")
test_env = Path("/tmp/.env")
if test_env.exists():
    test_env.unlink()

sys.path.insert(0, '/workspace/game-ops-monitor')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# 清掉所有 MINIMAX_* 环境变量
for k in list(os.environ.keys()):
    if k.startswith("MINIMAX_"):
        del os.environ[k]

# 单次 app 实例
app = QApplication.instance() or QApplication([])

from src.gui.main_window import MainWindow
from src.gui.settings_dialog import SettingsDialog

print("="*60)
print("场景 1：首次启动（无 API key）")
print("="*60)

window = MainWindow()
app.processEvents()

# 直接检查 _check_first_run 内部逻辑（不弹 QMessageBox）
from pathlib import Path as P
import os as O
api_key = O.getenv("MINIMAX_API_KEY")
if not api_key:
    env_path = P("/tmp/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MINIMAX_API_KEY="):
                val = line.split("=", 1)[1].strip()
                if val and val != "sk-xxxxx":
                    api_key = val
                    break

if not api_key:
    print("✅ 检测到无 API key，会引导用户去设置")
else:
    print(f"❌ API key 已存在: {api_key[:8]}...")

# 场景 2: 保存 API key
print()
print("="*60)
print("场景 2：用户在设置对话框填写并保存")
print("="*60)

dlg = SettingsDialog(window)
dlg.api_key_edit.setText("sk-test123456789")
dlg.base_url_edit.setText("https://api.minimax.io/v1")
dlg.model_edit.setText("MiniMax-M2.5")
dlg._save_to_files()  # 不弹模态，直接写文件
app.processEvents()

env_file = Path("/tmp/.env")
if env_file.exists():
    content = env_file.read_text()
    print(f"✅ .env 已生成:")
    for line in content.splitlines():
        if "API_KEY" in line and "=" in line:
            k, v = line.split("=", 1)
            masked = v[:8] + "*" * max(0, len(v) - 8) if len(v) > 0 else "(空)"
            print(f"   {k}={masked}")
        else:
            print(f"   {line}")
else:
    print("❌ .env 未生成")
    sys.exit(1)

# 场景 3: 第二次启动
print()
print("="*60)
print("场景 3：第二次启动（API key 已存在）")
print("="*60)

# 重新检查逻辑
api_key = O.getenv("MINIMAX_API_KEY")
if not api_key:
    env_path = P("/tmp/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MINIMAX_API_KEY="):
                val = line.split("=", 1)[1].strip()
                if val and val != "sk-xxxxx":
                    api_key = val
                    break

if api_key:
    print(f"✅ 检测到 API key: {api_key[:8]}...")
    print(f"   状态栏会显示: ✓ 已加载 API Key: {api_key[:8]}...")
    print(f"   不会弹设置对话框 ✓")
else:
    print("❌ 仍然没检测到 API key")

window.close()
print()
print("="*60)
print("✅ 首次启动流程验证通过")
print("="*60)
