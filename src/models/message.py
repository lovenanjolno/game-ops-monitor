"""
统一数据模型

所有 DataSource 抓取的消息都标准化为 RawMessage，
所有 Classifier 输出都标准化为 ClassificationResult。
这样新增数据源/分类器时，存储层、CLI、GUI 都不需要改动。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Source(str, Enum):
    """数据源类型"""
    GOOGLE_PLAY = "google_play"
    DISCORD = "discord"
    APP_STORE = "app_store"  # 预留
    STEAM = "steam"          # 预留


class Category(str, Enum):
    """客诉分类"""
    GAMEPLAY = "gameplay"           # 游戏性问题
    CONFLICT = "conflict"           # 玩家间冲突
    TECH = "tech"                   # 系统兼容性
    MONETIZATION = "monetization"   # 商业相关
    NOT_COMPLAINT = None            # 非客诉（用 None 表示，避免误判）


class RawMessage(BaseModel):
    """
    标准化原始消息
    
    任何 DataSource 抓取到的内容都必须转成这个格式。
    """
    # 来源标识
    source: Source = Field(..., description="数据源类型")
    source_id: str = Field(..., description="原始消息 ID（用于去重）")
    target_id: str = Field(..., description="抓取目标 ID（包名/频道 ID）")
    target_name: Optional[str] = Field(None, description="抓取目标名称（游戏名/频道名）")
    
    # 消息内容
    author: str = Field(..., description="作者名/ID")
    content: str = Field(..., description="消息正文")
    
    # 元数据
    timestamp: datetime = Field(..., description="消息时间")
    url: Optional[str] = Field(None, description="原帖链接（用于 GUI 跳转）")
    rating: Optional[int] = Field(None, ge=1, le=5, description="评分（仅 Google Play）")
    
    # 扩展字段（保留灵活性）
    metadata: dict = Field(default_factory=dict, description="数据源特定的元数据")
    
    class Config:
        use_enum_values = True


class ClassificationResult(BaseModel):
    """LLM 分类结果"""
    is_complaint: bool = Field(..., description="是否为客诉")
    category: Optional[Category] = Field(None, description="客诉分类（非客诉为 None）")
    urgency: int = Field(..., ge=1, le=5, description="紧急度 1-5")
    summary: str = Field(..., max_length=100, description="一句话摘要")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="置信度（可选）")
    raw_response: Optional[str] = Field(None, description="LLM 原始响应（调试用）")
    
    class Config:
        use_enum_values = True


class MonitoredItem(BaseModel):
    """
    抓取 + 分类后的完整记录（数据库存储格式）
    """
    message: RawMessage
    classification: ClassificationResult
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
