"""
配置加载
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载 .env
load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """
    加载配置

    优先级：环境变量 > .env 文件 > config.yaml > 默认值

    注意：即使 config.yaml 不存在，也会从环境变量读 key 和 base_url
    """
    # 关键修复：无论 config.yaml 是否存在，都先注入环境变量
    config = _default_config()

    # 1. 读 .env 文件（如果存在）— python-dotenv 会自动找当前 cwd
    #    load_dotenv() 已在模块顶部调用

    # 2. 读 config.yaml
    path = Path(config_path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}
            # 深度合并 yaml 配置（顶层 dict 完全替换）
            for key, value in yaml_config.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key].update(value)
                else:
                    config[key] = value
        except Exception as e:
            logger.warning(f"读 config.yaml 失败: {e}")
    else:
        logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")

    # 3. 注入环境变量（关键！无论 yaml 是否存在都执行）
    llm_config = config.setdefault("llm", {})
    api_key_env = llm_config.get("api_key_env", "MINIMAX_API_KEY")
    base_url_env = llm_config.get("base_url_env", "MINIMAX_BASE_URL")

    if os.getenv(api_key_env):
        llm_config["api_key"] = os.getenv(api_key_env)
    if os.getenv(base_url_env):
        llm_config["base_url"] = os.getenv(base_url_env)

    return config


def _default_config() -> dict:
    return {
        "sources": {
            "google_play": {"enabled": False, "targets": []},
            "discord": {"enabled": False, "targets": []},
        },
        "llm": {
            "provider": "minimax",
            "api_key_env": "MINIMAX_API_KEY",
            "base_url_env": "MINIMAX_BASE_URL",
            "model": "MiniMax-M2.5",
            "temperature": 0.1,
            # ⚠️ 国内默认 api.minimaxi.com，国际用 api.minimax.io
            # 请根据你的 key 来源选择
        },
        "storage": {"db_path": "data/monitor.db"},
        "classification": {
            "min_urgency_to_alert": 4,
            "skip_non_complaints": False,
        },
    }
