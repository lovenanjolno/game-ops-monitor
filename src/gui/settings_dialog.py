"""
设置对话框：API key / 数据源配置
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTabWidget, QWidget, QTextEdit, QMessageBox,
    QFileDialog, QGroupBox
)


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置")
        self.setMinimumSize(600, 500)
        self._build_ui()
        self._load_current()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        # ---- Tab 1: LLM 配置 ----
        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        llm_layout.setContentsMargins(16, 16, 16, 16)
        
        llm_form = QFormLayout()
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-xxxxx...")
        llm_form.addRow("API Key:", self.api_key_edit)
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setText("https://api.minimax.io/v1")
        llm_form.addRow("Base URL:", self.base_url_edit)
        
        self.model_edit = QLineEdit()
        self.model_edit.setText("MiniMax-M2.5")
        self.model_edit.setPlaceholderText("MiniMax-M2.5 / MiniMax-M3 / ...")
        llm_form.addRow("Model:", self.model_edit)
        
        llm_layout.addLayout(llm_form)
        
        info = QLabel(
            "💡 这些设置会保存到 <code>.env</code> 文件。<br>"
            "默认使用 <b>minimax</b>，兼容 OpenAI 协议的 LLM 都可填入。"
        )
        info.setStyleSheet("color: #666; padding: 8px; background: #f5f5f5; border-radius: 4px;")
        info.setWordWrap(True)
        llm_layout.addWidget(info)
        
        llm_layout.addStretch()
        
        # 测试连接
        test_btn = QPushButton("🧪 测试连接")
        test_btn.clicked.connect(self._test_llm)
        llm_layout.addWidget(test_btn)
        
        tabs.addTab(llm_tab, "🤖 LLM")
        
        # ---- Tab 2: 数据源 ----
        source_tab = QWidget()
        source_layout = QVBoxLayout(source_tab)
        source_layout.setContentsMargins(16, 16, 16, 16)
        
        config_path_label = QLabel("📁 配置文件: <code>config.yaml</code>")
        config_path_label.setStyleSheet("color: #666; padding: 4px 0;")
        source_layout.addWidget(config_path_label)
        
        self.config_text = QTextEdit()
        self.config_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        source_layout.addWidget(self.config_text)
        
        config_btn_layout = QHBoxLayout()
        
        open_btn = QPushButton("📂 打开文件")
        open_btn.clicked.connect(self._open_config_file)
        config_btn_layout.addWidget(open_btn)
        
        reload_btn = QPushButton("🔄 重新加载")
        reload_btn.clicked.connect(self._load_current)
        config_btn_layout.addWidget(reload_btn)
        
        config_btn_layout.addStretch()
        
        source_layout.addLayout(config_btn_layout)
        
        tabs.addTab(source_tab, "📡 数据源")
        
        # ---- Tab 3: 关于 ----
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setContentsMargins(16, 16, 16, 16)
        
        about_text = QLabel("""
<h2>🎮 Game Ops Monitor</h2>
<p>游戏运营客诉自动监控系统</p>
<p><b>版本:</b> 0.1.0</p>

<h3>架构</h3>
<ul>
<li>📡 数据源: Google Play (✅) / Discord (🔜)</li>
<li>🤖 分类: minimax LLM (OpenAI 兼容)</li>
<li>💾 存储: SQLite (本地)</li>
<li>🖥️ GUI: PyQt6</li>
</ul>

<h3>特性</h3>
<ul>
<li>多数据源架构，扩展无需改主流程</li>
<li>LLM 驱动分类（4 类 + 5 级紧急度）</li>
<li>异步抓取，不阻塞 UI</li>
<li>SQLite 本地存储，零运维</li>
</ul>

<p style="color: #888;">© 2026 Mavis</p>
        """)
        about_text.setWordWrap(True)
        about_text.setStyleSheet("line-height: 1.6;")
        about_layout.addWidget(about_text)
        about_layout.addStretch()
        
        tabs.addTab(about_tab, "ℹ️ 关于")
        
        layout.addWidget(tabs)
        
        # ---- 底部按钮 ----
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("💾 保存")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_current(self):
        """加载当前配置"""
        # .env
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("MINIMAX_API_KEY="):
                    self.api_key_edit.setText(line.split("=", 1)[1].strip())
                elif line.startswith("MINIMAX_BASE_URL="):
                    self.base_url_edit.setText(line.split("=", 1)[1].strip())
                elif line.startswith("MINIMAX_MODEL="):
                    self.model_edit.setText(line.split("=", 1)[1].strip())
        
        # config.yaml
        config_path = Path("config.yaml")
        if config_path.exists():
            self.config_text.setPlainText(config_path.read_text(encoding="utf-8"))
        else:
            self.config_text.setPlainText("# 配置文件不存在")
    
    def _save(self):
        """保存配置（UI 入口：保存 + 弹成功提示）"""
        try:
            self._save_to_files()
            QMessageBox.information(self, "成功", "配置已保存")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def _save_to_files(self):
        """
        真正写文件（无 UI 副作用，可测试）
        
        Returns:
            dict: {"env_path": "...", "config_path": "..." or None}
        """
        # 保存 .env
        env_path = Path(".env")
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        
        new_env = {
            "MINIMAX_API_KEY": self.api_key_edit.text().strip(),
            "MINIMAX_BASE_URL": self.base_url_edit.text().strip(),
            "MINIMAX_MODEL": self.model_edit.text().strip(),
        }
        
        for key, value in new_env.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{key}="):
                    env_lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                env_lines.append(f"{key}={value}")
        
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        
        # 保存 config.yaml（如果有修改）
        config_path = None
        config_text = self.config_text.toPlainText()
        if config_text and not config_text.startswith("# 配置文件不存在"):
            config_path = Path("config.yaml")
            config_path.write_text(config_text, encoding="utf-8")
        
        return {"env_path": str(env_path), "config_path": str(config_path) if config_path else None}
    
    def _test_llm(self):
        """测试 LLM 连接"""
        from PyQt6.QtWidgets import QApplication
        
        # 临时设置环境变量
        os.environ["MINIMAX_API_KEY"] = self.api_key_edit.text().strip()
        os.environ["MINIMAX_BASE_URL"] = self.base_url_edit.text().strip()
        os.environ["MINIMAX_MODEL"] = self.model_edit.text().strip()
        
        try:
            from ..classifier import LLMClassifier
            classifier = LLMClassifier()
            
            from ..models import RawMessage, Source
            from datetime import datetime
            
            test_msg = RawMessage(
                source=Source.GOOGLE_PLAY,
                source_id="test",
                target_id="test",
                author="tester",
                content="游戏闪退",
                timestamp=datetime.utcnow(),
            )
            result = classifier.classify(test_msg)
            
            QMessageBox.information(
                self,
                "测试成功",
                f"✓ LLM 连接正常\n\n"
                f"分类: {result.category}\n"
                f"紧急度: {result.urgency}\n"
                f"摘要: {result.summary}\n"
                f"置信度: {result.confidence}"
            )
        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"❌ {type(e).__name__}: {e}")
    
    def _open_config_file(self):
        """用系统默认编辑器打开 config.yaml"""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        config_path = Path("config.yaml").absolute()
        if config_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(config_path)))
