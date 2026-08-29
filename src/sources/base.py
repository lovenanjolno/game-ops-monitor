"""
DataSource 抽象基类

所有数据源（Google Play、Discord、App Store 等）都继承这个接口。
新增数据源 = 写一个新文件，主流程零改动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field

from ..models import RawMessage, Source


class Target(BaseModel):
    """可监控的目标（一个游戏、一个频道等）"""
    id: str = Field(..., description="唯一标识（包名/频道 ID）")
    name: str = Field(..., description="显示名称")
    enabled: bool = Field(True, description="是否启用")
    extra: dict = Field(default_factory=dict, description="数据源特定参数")


class DataSource(ABC):
    """
    数据源抽象基类
    
    设计原则：
    - 拉取和监听分离：fetch 主动拉取，listen 实时订阅（可选实现）
    - 配置驱动：所有 targets 来自配置文件
    - 输出标准化：所有消息统一为 RawMessage
    """
    
    source_name: Source  # 子类必须指定
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
    
    @abstractmethod
    def fetch(self, target_id: str, limit: int = 50, **kwargs) -> list[RawMessage]:
        """
        主动拉取消息/评论
        
        Args:
            target_id: 目标 ID（包名/频道 ID）
            limit: 拉取条数
            **kwargs: 数据源特定参数（如 lang, country）
        
        Returns:
            标准化后的 RawMessage 列表
        """
        ...
    
    @abstractmethod
    def list_targets(self) -> list[Target]:
        """列出此数据源可监控的目标（供 GUI 下拉框、配置校验用）"""
        ...
    
    def validate(self) -> bool:
        """验证数据源配置是否可用（API key、token 等）"""
        return True
    
    # -------- 可选实现 --------
    
    def listen(self, target_id: str, callback, **kwargs):
        """
        实时监听（可选）。Discord 等支持实时推送的数据源可实现。
        Google Play 没有实时推送，所以不实现。
        """
        raise NotImplementedError(
            f"{self.source_name} 不支持实时监听（仅支持主动拉取）"
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name}>"
