"""
Google Play 商店评论抓取

使用 google-play-scraper 库（开源、无需 API key、支持多语言区域）。
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import Optional
from datetime import datetime, timedelta
from urllib.parse import quote

from google_play_scraper import reviews as gp_reviews, Sort, app as gp_app

from .base import DataSource, Target
from ..models import RawMessage, Source

logger = logging.getLogger(__name__)


# "全球"模式：遍历这些主要地区，合并去重
# 选择标准：Google Play 主流市场 + 用户量大
GLOBAL_REGIONS = [
    ("us", "en"),   # 美国
    ("cn", "zh"),   # 中国
    ("jp", "ja"),   # 日本
    ("kr", "ko"),   # 韩国
    ("gb", "en"),   # 英国
    ("de", "de"),   # 德国
    ("fr", "fr"),   # 法国
    ("br", "pt"),   # 巴西
    ("in", "en"),   # 印度
    ("ru", "ru"),   # 俄罗斯
    ("tw", "zh"),   # 台湾
    ("hk", "zh"),   # 香港
]


class GooglePlaySource(DataSource):
    """Google Play 商店评论数据源"""
    
    source_name = Source.GOOGLE_PLAY
    
    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.default_country = self.config.get("default_country", "cn")
        self.default_lang = self.config.get("default_lang", "zh")
        # 缓存包名 → 应用名（避免每次都请求）
        self._product_name_cache: dict[str, str] = {}

    def _get_product_name(self, target_id: str, country: str = "us", lang: str = "en") -> str:
        """查询应用名（包名 → "Clash Royale" 这种），失败时回退包名"""
        if target_id in self._product_name_cache:
            return self._product_name_cache[target_id]

        try:
            info = gp_app(target_id, lang=lang, country=country)
            title = info.get("title") or info.get("appId") or target_id
        except Exception as e:
            logger.warning(f"[GooglePlay] 取应用名失败 {target_id}: {e}")
            title = target_id

        self._product_name_cache[target_id] = title
        return title
    
    def fetch(
        self,
        target_id: str,
        limit: int = 50,
        country: Optional[str] = None,
        lang: Optional[str] = None,
        days: Optional[int] = None,
        **kwargs
    ) -> list[RawMessage]:
        """
        抓取 Google Play 应用的评论
        
        Args:
            target_id: Android 包名，如 com.supercell.clashroyale
            limit: 抓取条数（实际可能略多于 limit，因为有 continuation token）
            country: 国家代码，如 cn / us
            lang: 语言代码，如 zh / en
            days: 只保留最近 N 天的评论（None = 不限）
        
        Returns:
            标准化后的 RawMessage 列表
        """
        country = country or self.default_country
        lang = lang or self.default_lang
        
        # 如果有时间范围，多拉一些再过滤（避免拉到太老的）
        fetch_count = limit * 3 if days else limit
        
        logger.info(
            f"[GooglePlay] 抓取 {target_id} (country={country}, lang={lang}, "
            f"limit={limit}, days={days})"
        )
        
        # google-play-scraper 没暴露 timeout，用线程 + 手动超时包装
        timeout_seconds = 30
        
        def _do_fetch():
            return gp_reviews(
                target_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=fetch_count,
            )
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_fetch)
                try:
                    results, _ = future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.error(
                        f"[GooglePlay] 抓取超时（{timeout_seconds}s）"
                        f" 可能是网络问题或包名错误"
                    )
                    return []
        except Exception as e:
            logger.error(f"[GooglePlay] 抓取失败: {e}")
            return []
        
        messages = []
        cutoff_time = None
        if days is not None:
            cutoff_time = datetime.utcnow() - timedelta(days=days)

        # 抓应用名（一次即可，写到每条的 metadata 里）
        product_name = self._get_product_name(target_id, country=country, lang=lang)

        for r in results:
            try:
                # 时间过滤
                if cutoff_time is not None:
                    at = r.get("at")
                    if at and isinstance(at, datetime):
                        # google-play-scraper 用本地时区，转 UTC 比较
                        if at.replace(tzinfo=None) < cutoff_time:
                            continue
                
                msg = self._to_raw_message(r, target_id, country, lang, product_name=product_name)
                messages.append(msg)
                
                # 达到 limit 就停
                if len(messages) >= limit:
                    break
            except Exception as e:
                logger.warning(f"[GooglePlay] 跳过一条解析失败的消息: {e}")
                continue
        
        logger.info(f"[GooglePlay] 成功抓取 {len(messages)} 条评论")
        return messages
    
    def _to_raw_message(
        self, review: dict, target_id: str, country: str, lang: str,
        product_name: str = "",
    ) -> RawMessage:
        """将 google-play-scraper 返回的 dict 转成 RawMessage"""
        review_id = review.get("reviewId", "")
        user_name = review.get("userName", "Anonymous")
        content = review.get("content", "")
        score = review.get("score")

        # 时间处理
        at = review.get("at")
        if isinstance(at, datetime):
            timestamp = at
        elif at:
            timestamp = at
        else:
            timestamp = datetime.utcnow()

        # 构造原帖 URL
        url = f"https://play.google.com/store/apps/details?id={target_id}&reviewId={review_id}"

        # 元数据
        metadata = {
            "country": country,
            "lang": lang,
            "thumbs_up": review.get("thumbsUpCount", 0),
            "reply_content": review.get("replyContent"),
            "reply_at": review.get("repliedAt").isoformat() if review.get("repliedAt") else None,
            "product_name": product_name,  # 应用名（"Clash Royale" 这种）
        }

        return RawMessage(
            source=Source.GOOGLE_PLAY,
            source_id=review_id,
            target_id=target_id,
            target_name=product_name or target_id,  # 目标名优先用产品名
            author=user_name,
            content=content,
            timestamp=timestamp,
            url=url,
            rating=score,
            metadata=metadata,
        )
    
    def fetch_global(
        self,
        target_id: str,
        limit: int = 50,
        max_regions: int = 6,
        days: Optional[int] = None,
    ) -> list[RawMessage]:
        """
        抓取多地区评论，合并去重
        
        Args:
            target_id: 包名
            limit: 最终返回条数
            max_regions: 最多抓几个地区（默认 6，控制时间）
            days: 时间范围
        """
        # 用 source_id + content 组合去重（同一评论可能在多地区出现）
        seen = set()
        all_messages = []
        
        regions_to_try = GLOBAL_REGIONS[:max_regions]
        logger.info(
            f"[GooglePlay] 全球抓取 {target_id}，"
            f"将遍历 {len(regions_to_try)} 个地区: "
            f"{[c for c, _ in regions_to_try]}"
        )
        
        for country, lang in regions_to_try:
            try:
                msgs = self.fetch(
                    target_id=target_id,
                    limit=limit,
                    country=country,
                    lang=lang,
                    days=days,
                )
                added = 0
                for m in msgs:
                    # 用 source_id 唯一标识 + content 兜底去重
                    dedup_key = (m.source_id, m.content[:50])
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        all_messages.append(m)
                        added += 1
                
                logger.info(
                    f"[GooglePlay]   {country}/{lang}: "
                    f"抓到 {len(msgs)} 条, 新增 {added} 条, 累计 {len(all_messages)}"
                )
                
                # 已经够了就停
                if len(all_messages) >= limit:
                    break
            except Exception as e:
                logger.warning(f"[GooglePlay]   {country}/{lang} 失败: {e}")
                continue
        
        # 按时间倒序
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)
        result = all_messages[:limit]
        logger.info(
            f"[GooglePlay] 全球抓取完成: {len(result)} 条 (去重后)"
        )
        return result
    
    def list_targets(self) -> list[Target]:
        """
        列出配置中可监控的应用。
        注意：Google Play 没有"列出所有应用"的 API（除非你是开发者），
        所以这里从配置读取。
        """
        targets_config = self.config.get("targets", [])
        return [
            Target(
                id=t["id"],
                name=t.get("name", t["id"]),
                enabled=t.get("enabled", True),
                extra={
                    "country": t.get("country", self.default_country),
                    "lang": t.get("lang", self.default_lang),
                },
            )
            for t in targets_config
        ]
    
    def validate(self) -> bool:
        # google-play-scraper 无需认证，但可以快速试一个请求验证连通性
        try:
            gp_reviews(
                "com.android.settings",  # 系统应用，永远存在
                lang="en",
                country="us",
                count=1,
            )
            return True
        except Exception as e:
            logger.error(f"[GooglePlay] 验证失败: {e}")
            return False
