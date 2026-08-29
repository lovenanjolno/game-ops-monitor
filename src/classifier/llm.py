"""
LLM 分类器（minimax 适配）

通过 OpenAI 兼容协议调用 minimax API。
可以一行配置切换到任何兼容 OpenAI 协议的 LLM。
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from openai import OpenAI

from .base import Classifier
from ..models import RawMessage, ClassificationResult, Category

logger = logging.getLogger(__name__)


# 默认分类 prompt
DEFAULT_PROMPT = """你是资深游戏运营分析师。分析以下玩家消息，判断：

1. **is_complaint**（是否为客诉）：
   - 单纯表扬、闲聊、提问建议 → false
   - 表达不满、报告问题、请求帮助解决 → true

2. **category**（客诉分类，is_complaint=true 时必填）：
   - "gameplay" - 游戏性问题（数值、平衡、玩法、剧情、难度）
   - "conflict" - 玩家间冲突（骂人、PVP 不公、外挂举报、恶意组队）
   - "tech" - 系统兼容性（闪退、卡顿、崩溃、无法登录、网络、发热）
   - "monetization" - 商业相关（充值不到账、定价过贵、活动坑、抽奖概率）
   - "other" - 其他不属于上述任何分类的客诉

3. **urgency**（紧急度 1-5）：
   - 1: 轻微吐槽，无实质问题
   - 2: 一般抱怨，不影响游戏
   - 3: 明显不满，影响部分功能
   - 4: 爆发风险/群体性，财务损失预警
   - 5: 已造成损失（充值不到账、封号误判、大规模闪退）

4. **summary**：一句话中文摘要，≤20 字，抓住核心问题

5. **confidence**：置信度 0-1

⚠️ 重要：只输出一个 JSON 对象，不要任何思考过程、解释或 markdown 包裹。
直接以 {{ 开头，以 }} 结尾。

玩家消息：
\"\"\"{content}\"\"\"
"""


class LLMClassifier(Classifier):
    """LLM 驱动的分类器"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        prompt_template: Optional[str] = None,
        temperature: float = 0.1,
    ):
        # 默认从环境变量读取
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        # 默认 base_url: 国内 minimax (platform.minimaxi.com)
        # 国际用户需要设置 MINIMAX_BASE_URL=https://api.minimax.io/v1
        self.base_url = base_url or os.getenv(
            "MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"
        )
        self.model = model or os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")
        self.prompt_template = prompt_template or DEFAULT_PROMPT
        self.temperature = temperature
        
        if not self.api_key:
            raise ValueError(
                "未设置 MINIMAX_API_KEY。"
                "请在 .env 文件中设置，或传入 api_key 参数。"
            )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        
        logger.info(
            f"[LLMClassifier] 初始化: model={self.model}, base_url={self.base_url}"
        )
    
    def classify(self, message: RawMessage) -> ClassificationResult:
        """分类单条消息"""
        prompt = self.prompt_template.format(content=message.content)

        try:
            # 尝试使用 json_object 模式 + 关闭 reasoning（minimax M2.5/M3 默认开启）
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    extra_body={"reasoning_split": False},
                )
            except Exception:
                # 降级：去掉 json_object
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                        extra_body={"reasoning_split": False},
                    )
                except Exception:
                    # 再降级：什么都不加
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )

            raw_text = response.choices[0].message.content
            # 如果 minimax 返回了 reasoning_details（即使我们要求不分），也忽略它
            # 强制只用 .content 字段
            return self._parse_response(raw_text or "")

        except Exception as e:
            logger.error(f"[LLMClassifier] 分类失败: {e}")
            return ClassificationResult(
                is_complaint=False,
                category=None,
                urgency=1,
                summary=f"[分类失败: {type(e).__name__}]",
                confidence=0.0,
                raw_response=str(e),
            )
    
    def classify_batch(
        self, messages: list[RawMessage], concurrency: int = 5
    ) -> list[ClassificationResult]:
        """
        批量分类（带并发）
        
        注：真正的高并发需要异步。当前实现是顺序的，
        后续可改为 asyncio + semaphore。
        """
        logger.info(f"[LLMClassifier] 批量分类 {len(messages)} 条消息")
        results = []
        for i, msg in enumerate(messages, 1):
            result = self.classify(msg)
            results.append(result)
            if i % 10 == 0:
                logger.info(f"[LLMClassifier] 进度: {i}/{len(messages)}")
        return results
    
    def _parse_response(self, raw_text: str) -> ClassificationResult:
        """解析 LLM 响应（兼容 <think> 块、markdown 包裹、纯文本）"""
        text = raw_text.strip()

        # 1. 剥掉 <think>...</think> 块（minimax M2.5/M3 默认行为）
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. 剥掉 markdown 代码块包裹
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # 3. 如果有多个 JSON 对象，只取第一个完整的
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if json_match:
            text = json_match.group(0)

        # 4. 尝试 json.loads
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[LLMClassifier] JSON 解析失败: {e}, raw={text[:200]}")
            # 5. fallback: 用正则提取
            data = self._extract_fallback(text)
            if not data:
                # 还是失败，返回一个安全的默认值
                return ClassificationResult(
                    is_complaint=False,
                    category=None,
                    urgency=1,
                    summary="[解析失败]",
                    confidence=0.0,
                    raw_response=raw_text,
                )

        # 解析 category
        category_str = data.get("category")
        category = None
        if category_str and category_str != "null":
            try:
                category = Category(category_str)
            except ValueError:
                logger.warning(f"[LLMClassifier] 未知 category: {category_str}")
                category = None

        return ClassificationResult(
            is_complaint=bool(data.get("is_complaint", False)),
            category=category,
            urgency=int(data.get("urgency", 1)),
            summary=str(data.get("summary", ""))[:100],
            confidence=float(data.get("confidence", 0.5)) if data.get("confidence") is not None else None,
            raw_response=raw_text,
        )
    
    def _extract_fallback(self, text: str) -> dict:
        """JSON 解析失败时的正则提取"""
        result = {
            "is_complaint": False,
            "category": None,
            "urgency": 1,
            "summary": "[解析失败]",
            "confidence": 0.0,
        }
        
        if re.search(r'"is_complaint"\s*:\s*true', text, re.IGNORECASE):
            result["is_complaint"] = True
        
        cat_match = re.search(
            r'"category"\s*:\s*"?(gameplay|conflict|tech|monetization)"?',
            text, re.IGNORECASE
        )
        if cat_match:
            result["category"] = cat_match.group(1).lower()
        
        urg_match = re.search(r'"urgency"\s*:\s*([1-5])', text)
        if urg_match:
            result["urgency"] = int(urg_match.group(1))
        
        return result
