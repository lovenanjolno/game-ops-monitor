# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 - GUI 版本

使用方法：
    pip install pyinstaller
    pyinstaller game_ops_monitor.spec

或用 build.py 一键打包：
    python build.py --gui
"""
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(SPECPATH)

block_cipher = None

# 收集所有数据文件
datas = [
    # 配置文件
    ('config.yaml', '.'),
    ('.env.example', '.'),
]

# 隐藏导入（PyInstaller 静态分析漏掉的）
hiddenimports = [
    # sqlite3 标准库
    'sqlite3',
    # 我们的模块
    'src',
    'src.cli',
    'src.gui_main',
    'src.config',
    'src.models',
    'src.models.message',
    'src.sources',
    'src.sources.base',
    'src.sources.google_play',
    'src.sources.discord',
    'src.sources.factory',
    'src.classifier',
    'src.classifier.base',
    'src.classifier.llm',
    'src.storage',
    'src.storage.sqlite_store',
    'src.gui',
    'src.gui.main_window',
    'src.gui.widgets.source_panel',
    'src.gui.widgets.overview',
    'src.gui.widgets.complaint_list',
    'src.gui.widgets.detail_panel',
    'src.gui.settings_dialog',
    'src.gui.workers.fetch_worker',
    # 第三方库
    'google_play_scraper',
    'google_play_scraper.features',
    'google_play_scraper.features.reviews',
    'openai',
    'pydantic',
    'yaml',
    'dotenv',
    # PyQt6
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
]

# 排除不需要的库（减小体积）
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'pytest',
    'setuptools',
    'pip',
    'wheel',
    # PyQt6 不需要的模块
    'PyQt6.QtBluetooth',
    'PyQt6.QtDBus',
    'PyQt6.QtDesigner',
    'PyQt6.QtHelp',
    'PyQt6.QtLocation',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtNfc',
    'PyQt6.QtOpenGL',
    'PyQt6.QtOpenGLWidgets',
    'PyQt6.QtPdf',
    'PyQt6.QtPdfWidgets',
    'PyQt6.QtPositioning',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtQml',
    'PyQt6.QtQuick',
    'PyQt6.QtQuickWidgets',
    'PyQt6.QtRemoteObjects',
    'PyQt6.QtScxml',
    'PyQt6.QtSensors',
    'PyQt6.QtSerialPort',
    'PyQt6.QtSql',
    'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets',
    'PyQt6.QtTest',
    'PyQt6.QtWebChannel',
    'PyQt6.QtWebSockets',
    'PyQt6.QtXml',
]

a = Analysis(
    [str(ROOT / 'src' / 'gui_main.py')],  # ✅ GUI 入口
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GameOpsMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # ✅ GUI 模式不弹黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'icon.ico') if (ROOT / 'assets' / 'icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GameOpsMonitor',
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name='GameOpsMonitor.app',
    icon=str(ROOT / 'assets' / 'icon.icns') if (ROOT / 'assets' / 'icon.icns').exists() else None,
    bundle_identifier='com.gameops.monitor',
    info_plist={
        'CFBundleName': 'GameOpsMonitor',
        'CFBundleDisplayName': 'Game Ops Monitor',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '0.1.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13',
    },
)
