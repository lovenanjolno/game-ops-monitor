# 打包说明

把 Game Ops Monitor 打包成单文件可执行程序，运营同事双击就能用，无需安装 Python。

## 前置条件

1. Python 3.11+
2. 项目依赖已安装：`pip install -r requirements.txt`
3. PyInstaller：`pip install pyinstaller`
4. （可选）UPX：用于压缩，减小产物体积

## 一键打包

```bash
# 当前平台，默认 CLI 模式
python build.py

# 清理后重新打包
python build.py --clean

# 单文件模式（分发更简单，启动慢 5-10s）
python build.py --onefile
```

打包完成后产物在 `dist/` 目录。

## 跨平台

PyInstaller **不支持跨平台编译**——必须在目标平台打包：

| 目标平台 | 在什么系统打包 | 产物 |
|---------|--------------|------|
| Windows .exe | Windows 或带 wine 的 Linux | `dist/GameOpsMonitor.exe` |
| macOS .app | macOS | `dist/GameOpsMonitor.app` |
| Linux AppImage | Linux | `dist/GameOpsMonitor/GameOpsMonitor` |

要给 Windows 同事发包？找一台 Windows 机器（或用 GitHub Actions）跑 `python build.py`。

## 减小体积

默认配置已经做了：
- 排除 `numpy/pandas/matplotlib` 等大库
- 启用 UPX 压缩
- 排除 `tkinter`、`pytest` 等

如果还要更小：
```bash
# 用虚拟环境打包（只装需要的库）
python -m venv .venv-build
source .venv-build/bin/activate
pip install -r requirements.txt pyinstaller
python build.py
```

实测体积：
- 全量依赖：~100 MB
- 虚拟环境最小化：~70 MB

## GUI 阶段

GUI 完成后，需要修改 `src/cli.py` 入口指向 `src/gui/main.py`，或者在 `build.py` 里加个分支：

```python
# build.py
if gui:
    spec = 'game_ops_monitor_gui.spec'
else:
    spec = 'game_ops_monitor.spec'
```

并把 spec 文件里的 `console=True` 改为 `False`（不弹黑框）。

## 图标

把 `.ico`（Windows）和 `.icns`（macOS）放到 `assets/` 目录，spec 文件会自动用。
在线工具：https://convertico.com/

## 分发建议

### 方式 1：直接发 exe
最简单，但每次更新要让同事重下。

### 方式 2：用安装包
- Windows：NSIS / Inno Setup
- macOS：DMG
- Linux：AppImage

### 方式 3：自动更新
PyInstaller 产物可以配合 `pyinstaller-auto-update` 或自己写个启动器检测更新。

## 常见问题

**Q: 启动报错 "Failed to load Qt platform plugin"**
A: PyQt6 打包问题，加 `--collect-all PyQt6` 重新打包。

**Q: 找不到 .env / config.yaml**
A: PyInstaller 不会自动包含文本文件，已在 spec 的 `datas` 里加了。如果还不行，用 `--add-data`。

**Q: openai 调用失败**
A: 检查 .env 文件是否在 exe 同目录，或环境变量是否设置。

**Q: 杀软报警**
A: PyInstaller 产物经常被误报。可选：代码签名（要 EV 证书）、或用 Nuitka 编译。
