# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 - CLI 版本（不带 GUI）

适合在服务器、容器里用，或者给懂技术的同事体验。
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

datas = [
    ('config.yaml', '.'),
    ('.env.example', '.'),
]

hiddenimports = [
    'sqlite3',
    'src',
    'src.cli',
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
    'google_play_scraper',
    'google_play_scraper.features',
    'google_play_scraper.features.reviews',
    'openai',
    'pydantic',
    'yaml',
    'dotenv',
]

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
    'PyQt6',  # CLI 版不需要 PyQt6
]

a = Analysis(
    [str(ROOT / 'src' / 'cli.py')],
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
    name='GameOpsMonitor-CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # CLI 模式
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
    name='GameOpsMonitor-CLI',
)
