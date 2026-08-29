"""
Discord 数据源（占位实现）

⚠️ 当前为占位，待用户提供 Bot Token 后再实现。

实现步骤：
1. 安装依赖：pip install discord.py
2. 在 src/sources/discord.py 中实现 fetch / listen
3. 在 config.yaml 中配置 guild_id / channel_ids
4. 启用数据源：sources.discord.enabled = true

Discord API 参考：
- 官方文档：https://discord.com/developers/docs/intro
- Python SDK：https://discordpy.readthedocs.io/
- 必需权限：View Channels + Read Message History
- 必需 Intent：MESSAGE_CONTENT INTENT
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import DataSource, Target
from ..models import RawMessage, Source

logger = logging.getLogger(__name__)


class DiscordSource(DataSource):
    """Discord 频道消息数据源（占位）"""
    
    source_name = Source.DISCORD
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.token = self.config.get("token")
        if not self.token:
            logger.warning(
                "[Discord] 未配置 token，DiscordSource 不可用。"
                "请在 config.yaml 或环境变量 DISCORD_BOT_TOKEN 中设置。"
            )
    
    def fetch(self, target_id: str, limit: int = 50, **kwargs) -> list[RawMessage]:
        """
        拉取 Discord 频道历史消息
        
        实现参考（待填写）：
        ```python
        import discord
        
        intents = discord.Intents.default()
        intents.message_content = True  # 必需！
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            channel = client.get_channel(int(target_id))
            async for msg in channel.history(limit=limit):
                # 转 RawMessage
                ...
        ```
        """
        raise NotImplementedError(
            "Discord 数据源待实现。\n"
            "请参考本文件的 docstring 完成 fetch() 方法，"
            "或在 config.yaml 中暂时禁用 discord: enabled: false"
        )
    
    def list_targets(self) -> list[Target]:
        """列出可监控的 Discord 频道"""
        targets_config = self.config.get("targets", [])
        return [
            Target(
                id=t.get("channel_id", ""),
                name=t.get("name", t.get("channel_id", "")),
                enabled=t.get("enabled", True),
                extra={
                    "guild_id": t.get("guild_id"),
                    "guild_name": t.get("guild_name"),
                },
            )
            for t in targets_config
        ]
    
    def validate(self) -> bool:
        if not self.token:
            return False
        # TODO: 实现连接测试
        return True
    
    def listen(self, target_id: str, callback, **kwargs):
        """
        实时监听 Discord 消息（Discord 优势所在）
        
        实现参考（待填写）：
        ```python
        @client.event
        async def on_message(message):
            if str(message.channel.id) == target_id:
                raw = self._to_raw_message(message)
                callback(raw)
        ```
        """
        raise NotImplementedError("Discord 实时监听待实现")
