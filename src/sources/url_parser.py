"""
URL 解析器：从各种格式的 Google Play 链接中提取包名

支持的格式：
- https://play.google.com/store/apps/details?id=com.xxx
- https://play.google.com/store/apps/details?id=com.xxx&hl=zh
- https://play.google.com/store/apps/dev?id=123 → 需查询（不实现）
- https://play.app.goo.gl/?link=... → 短链
- 直接包名: com.xxx
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, parse_qs


# Google Play 包名正则（保守起见，要求至少有一段点号）
PACKAGE_NAME_RE = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$"
)


def parse_google_play_url(text: str) -> Optional[str]:
    """
    从输入中提取 Google Play 包名
    
    Args:
        text: 用户输入（可能是完整 URL 或直接包名）
    
    Returns:
        包名（小写），如果无法解析返回 None
    """
    if not text:
        return None
    
    text = text.strip()
    
    # 情况 1：直接就是包名
    if PACKAGE_NAME_RE.match(text):
        return text.lower()
    
    # 情况 2：标准 URL（支持所有 Google Play 子域名和路径）
    if any(domain in text for domain in [
        "play.google.com",
        "play.app.goo.gl",
        "play.google.com/pc-store",  # Google Play Games (PC)
        "play.google.com/store",     # 标准商店
    ]):
        return _extract_from_url(text)
    
    # 情况 3：粘了空格或换行的包名
    parts = text.split()
    for part in parts:
        if PACKAGE_NAME_RE.match(part):
            return part.lower()
    
    return None


def _extract_from_url(url: str) -> Optional[str]:
    """从 URL 字符串提取包名"""
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        # 1. ?id=com.xxx (覆盖所有 Google Play URL 变体)
        if "id" in query:
            pkg = query["id"][0]
            if PACKAGE_NAME_RE.match(pkg):
                return pkg.lower()

        # 2. 短链里嵌的 link 参数: play.app.goo.gl/?link=...
        if "link" in query:
            link_url = query["link"][0]
            # 递归处理
            inner = _extract_from_url(link_url)
            if inner:
                return inner

        # 3. 路径里有可能是包名（兜底）
        path_parts = [p for p in parsed.path.split("/") if p]
        for part in path_parts:
            if PACKAGE_NAME_RE.match(part):
                return part.lower()

        return None

    except Exception:
        return None


def is_valid_package_name(name: str) -> bool:
    """验证是否为合法 Android 包名"""
    return bool(PACKAGE_NAME_RE.match(name))


if __name__ == "__main__":
    # 简单自测
    test_cases = [
        "https://play.google.com/store/apps/details?id=com.supercell.clashroyale",
        "https://play.google.com/store/apps/details?id=com.tencent.tmgp.sgame&hl=zh_CN",
        "com.supercell.brawlstars",
        "  com.miHoYo.GenshinImpact  ",
        "https://play.google.com/store/apps/details?id=com.nianticlabs.pokemongo&hl=en&gl=us",
        "https://play.app.goo.gl/?link=https://play.google.com/store/apps/details?id=com.test.app",
        # 新增：PC 平台 URL
        "https://play.google.com/pc-store/games/details?id=com.supercell.clashroyale&pcampaignid=xxx",
        "随便粘的文本",
        "",
    ]

    for tc in test_cases:
        result = parse_google_play_url(tc)
        print(f"  {repr(tc)[:60]:<62} → {result}")
