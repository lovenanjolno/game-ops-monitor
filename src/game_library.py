"""
游戏库管理：在 config.yaml 的 google_play.targets 里增删改查游戏

数据结构（每个游戏一条）：
{
  "id": "com.supercell.clashroyale",  # 包名，主键
  "name": "部落冲突",                  # 显示名
  "country": "cn",                    # 地区代码
  "lang": "zh",                       # 语言代码
  "limit": 50,                        # 抓取数量
  "days": 7,                          # 时间范围
  "notes": "核心产品",                 # 备注
  "enabled": true,                    # 是否启用
}

不做服务器、不做数据库。就是个本地 Python 类 + yaml 文件。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


# ---- 数据模型 ----

class Game:
    """一个游戏 = 一个监控目标"""
    def __init__(
        self,
        id: str = "",
        name: str = "",
        country: str = "cn",
        lang: str = "zh",
        limit: int = 50,
        days: int = 7,
        notes: str = "",
        enabled: bool = True,
    ):
        self.id = id
        self.name = name
        self.country = country
        self.lang = lang
        self.limit = limit
        self.days = days
        self.notes = notes
        self.enabled = enabled

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "lang": self.lang,
            "limit": self.limit,
            "days": self.days,
            "notes": self.notes,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Game":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            country=d.get("country", "cn"),
            lang=d.get("lang", "zh"),
            limit=int(d.get("limit", 50)),
            days=int(d.get("days", 7)),
            notes=d.get("notes", ""),
            enabled=bool(d.get("enabled", True)),
        )

    def display(self) -> str:
        """在列表里显示的文本"""
        flag = "🟢" if self.enabled else "⚫"
        return f"{flag} {self.name or '(未命名)'}  ·  {self.id}"


# ---- 库管理 ----

class GameLibrary:
    """游戏库：增删改查 + 持久化到 yaml"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.games: list[Game] = []
        self.reload()

    def reload(self):
        """从 yaml 重新加载游戏列表"""
        self.games = []
        path = Path(self.config_path)
        if not path.exists():
            logger.info(f"[GameLibrary] 配置文件不存在: {self.config_path}，创建空库")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"[GameLibrary] 读 config.yaml 失败: {e}")
            return

        # google_play.targets 是列表
        targets = (cfg.get("sources", {}).get("google_play", {}).get("targets", [])) or []
        for t in targets:
            if isinstance(t, dict) and t.get("id"):
                self.games.append(Game.from_dict(t))
        logger.info(f"[GameLibrary] 加载 {len(self.games)} 个游戏")

    def save(self) -> bool:
        """把游戏列表写回 yaml（保留其他配置）"""
        path = Path(self.config_path)
        cfg = {}
        # 1. 先读现有 config
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"[GameLibrary] 读现有 config 失败: {e}")

        # 2. 写入 google_play.targets
        sources = cfg.setdefault("sources", {})
        gp = sources.setdefault("google_play", {})
        gp["enabled"] = any(g.enabled for g in self.games)  # 有任何一个启用就算启用
        gp["targets"] = [g.to_dict() for g in self.games]

        # 3. 写回
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, indent=2)
            logger.info(f"[GameLibrary] 保存 {len(self.games)} 个游戏到 {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"[GameLibrary] 保存失败: {e}")
            return False

    def add(self, game: Game) -> bool:
        """添加一个游戏。已存在（id 重复）则返回 False"""
        if not game.id:
            return False
        if self.find_by_id(game.id) is not None:
            return False  # 重复
        self.games.append(game)
        return True

    def delete(self, game_id: str) -> bool:
        """按 id 删除。找到并删了返回 True"""
        for i, g in enumerate(self.games):
            if g.id == game_id:
                del self.games[i]
                return True
        return False

    def update(self, game: Game) -> bool:
        """按 id 更新。找到并改了返回 True"""
        for i, g in enumerate(self.games):
            if g.id == game_id_safe(game):
                g.name = game.name
                g.country = game.country
                g.lang = game.lang
                g.limit = game.limit
                g.days = game.days
                g.notes = game.notes
                g.enabled = game.enabled
                return True
        return False

    def find_by_id(self, game_id: str) -> Optional[Game]:
        for g in self.games:
            if g.id == game_id:
                return g
        return None

    def find_by_name(self, name: str) -> Optional[Game]:
        for g in self.games:
            if g.name == name:
                return g
        return None


def game_id_safe(game: Game) -> str:
    """避免在 update 里 shadow 外部 game.id"""
    return game.id
