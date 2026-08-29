"""
Classifier 抽象基类

当前只用 LLM 实现，但留好接口。
未来可加规则分类器（正则匹配关键词）、本地小模型分类器等。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawMessage, ClassificationResult


class Classifier(ABC):
    """分类器抽象基类"""
    
    @abstractmethod
    def classify(self, message: RawMessage) -> ClassificationResult:
        """对单条消息分类"""
        ...
    
    def classify_batch(self, messages: list[RawMessage]) -> list[ClassificationResult]:
        """批量分类（默认逐条调用，子类可重写以优化）"""
        return [self.classify(m) for m in messages]
