# 诊断：检查 detail_panel.py 是不是新版
import os
import re
from pathlib import Path

def check_file(rel_path, new_marker, old_marker):
    path = Path(rel_path)
    if not path.exists():
        print(f"❌ {rel_path} 不存在")
        return
    content = path.read_text(encoding='utf-8')
    print(f"\n=== {rel_path} ===")
    print(f"   修改时间: {path.stat().st_mtime}")
    if new_marker in content:
        print(f"   ✅ 新版（找到 '{new_marker}'）")
    elif old_marker in content:
        print(f"   ❌ 旧版（找到 '{old_marker}'），需要更新")
    else:
        print(f"   ❓ 未知版本（既找不到新标记也找不到旧标记）")

check_file("src/gui/widgets/detail_panel.py", "font-size: 13px", "setMinimumWidth(56)")
check_file("src/gui/main_window.py", "v0.6.3", "v0.6.2")

# 统计 __pycache__
pyc_count = 0
for root, dirs, files in os.walk("."):
    if ".venv" in root or ".git" in root:
        continue
    pyc_count += sum(1 for f in files if f.endswith(".pyc"))
    for d in list(dirs):
        if d == "__pycache__":
            pyc_count += 1
            dirs.remove(d)
print(f"\n=== 缓存统计 ===")
print(f"   __pycache__ 文件夹 + .pyc 文件数: {pyc_count}")
if pyc_count > 0:
    print("   ⚠️ 建议清理后重启")
