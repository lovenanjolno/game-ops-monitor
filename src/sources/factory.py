"""
数据源工厂

根据配置自动创建对应的 DataSource 实例。
GUI 和 CLI 都通过这个工厂获取数据源，不直接 new。
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import DataSource
from .google_play import GooglePlaySource
from .discord import DiscordSource
from ..models import Source

logger = logging.getLogger(__name__)


# 注册表：新增数据源只需在这里加一行
_REGISTRY: dict[Source, type[DataSource]] = {
    Source.GOOGLE_PLAY: GooglePlaySource,
    Source.DISCORD: DiscordSource,
}


class SourceFactory:
    """数据源工厂"""
    
    @staticmethod
    def create(source_type: Source, config: Optional[dict] = None) -> DataSource:
        """
        创建数据源实例
        
        Args:
            source_type: 数据源类型
            config: 数据源配置（来自 config.yaml 的 sources.<type> 节点）
        
        Raises:
            ValueError: 不支持的数据源类型
        """
        cls = _REGISTRY.get(source_type)
        if not cls:
            raise ValueError(
                f"不支持的数据源: {source_type}。"
                f"已注册: {list(_REGISTRY.keys())}"
            )
        return cls(config=config)
    
    @staticmethod
    def create_from_config(config: dict) -> dict[Source, DataSource]:
        """
        从完整配置创建所有启用的数据源
        
        Args:
            config: 完整配置（来自 config.yaml）
        
        Returns:
            {Source.GOOGLE_PLAY: instance, ...}
        """
        sources = {}
        sources_config = config.get("sources", {})
        
        for source_name, source_config in sources_config.items():
            if not source_config.get("enabled", False):
                logger.info(f"[Factory] 跳过禁用的数据源: {source_name}")
                continue
            
            try:
                source_type = Source(source_name)
                sources[source_type] = SourceFactory.create(source_type, source_config)
            except ValueError as e:
                logger.warning(f"[Factory] {e}")
            except Exception as e:
                logger.error(f"[Factory] 创建 {source_name} 失败: {e}")
        
        return sources
    
    @staticmethod
    def register(source_type: Source, source_class: type[DataSource]):
        """注册新的数据源类型（供插件/扩展用）"""
        _REGISTRY[source_type] = source_class
        logger.info(f"[Factory] 注册新数据源: {source_type} -> {source_class.__name__}")
