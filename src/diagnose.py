"""
诊断命令：详细输出每一步的中间结果，定位问题

用法：
    python -m src.diagnose --source google_play --target com.supercell.clashroyale --limit 3
    python -m src.diagnose --target com.supercell.clashroyale --limit 3 --all-regions
"""
import json
import logging
import sys
import time
from pathlib import Path

# 详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.sources import SourceFactory
from src.classifier import LLMClassifier
from src.models import Source


def diagnose(source_name: str, target_id: str, limit: int = 3,
             country: str = None, lang: str = None):
    print("="*70)
    print(f"🔍 诊断: source={source_name} target={target_id} limit={limit}")
    print("="*70)
    
    # ---- 1. 检查 API key ----
    print("\n[1] 检查 API Key")
    print("-"*70)
    import os
    api_key = os.getenv("MINIMAX_API_KEY")
    if api_key:
        masked = api_key[:8] + "*" * max(0, len(api_key) - 8)
        print(f"  ✓ MINIMAX_API_KEY 已设置: {masked}")
    else:
        # 试 .env
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("MINIMAX_API_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if val and val != "sk-xxxxx":
                        api_key = val
                        os.environ["MINIMAX_API_KEY"] = val
                        break
        if api_key:
            print(f"  ✓ 从 .env 加载: {api_key[:8]}***")
        else:
            print(f"  ❌ MINIMAX_API_KEY 未设置！")
            print(f"     解决：在 .env 中填入 API key，或")
            print(f"           export MINIMAX_API_KEY=sk-xxxxx")
            return
    
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")
    print(f"  base_url: {base_url}")
    print(f"  model: {model}")
    
    # ---- 2. 抓取 ----
    print(f"\n[2] 抓取 {limit} 条评论")
    print("-"*70)
    config = load_config()
    source_config = config.get("sources", {}).get(source_name, {})
    source = SourceFactory.create(Source(source_name), source_config)
    
    t0 = time.time()
    try:
        messages = source.fetch(
            target_id=target_id, limit=limit,
            country=country or "us", lang=lang or "en",
        )
    except Exception as e:
        print(f"  ❌ 抓取异常: {type(e).__name__}: {e}")
        return
    
    elapsed = time.time() - t0
    print(f"  ✓ 抓取完成: {len(messages)} 条, 耗时 {elapsed:.1f}s")
    
    if not messages:
        print(f"  ⚠️  没拉到评论")
        print(f"     可能原因：")
        print(f"     1. 包名错误：{target_id} 不存在")
        print(f"     2. 该 app 在该地区/语言下没评论")
        print(f"     3. 网络问题（Google Play 限流）")
        return
    
    for i, m in enumerate(messages, 1):
        print(f"\n  [{i}] {m.author} | {m.rating}⭐ | {m.timestamp}")
        print(f"      内容: {m.content[:120]}{'...' if len(m.content) > 120 else ''}")
    
    # ---- 3. LLM 测试 ----
    print(f"\n[3] LLM 分类测试")
    print("-"*70)
    
    try:
        classifier = LLMClassifier()
        print(f"  ✓ LLMClassifier 初始化成功")
    except Exception as e:
        print(f"  ❌ LLMClassifier 初始化失败: {e}")
        return
    
    # 单条测试
    test_msg = messages[0]
    print(f"\n  测试第 1 条分类...")
    print(f"  内容: {test_msg.content[:80]}...")
    print(f"  调用 LLM...")
    
    t0 = time.time()
    try:
        result = classifier.classify(test_msg)
        elapsed = time.time() - t0
        print(f"  ✓ 分类成功 (耗时 {elapsed:.1f}s)")
        print(f"  结果:")
        print(f"    is_complaint: {result.is_complaint}")
        print(f"    category:     {result.category}")
        print(f"    urgency:      {result.urgency}")
        print(f"    summary:      {result.summary}")
        print(f"    confidence:   {result.confidence}")
        if result.raw_response:
            print(f"  原始响应（前 300 字符）:")
            print(f"    {result.raw_response[:300]}")
    except Exception as e:
        print(f"  ❌ 分类异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ---- 4. 批量 ----
    print(f"\n[4] 批量分类剩余 {len(messages)-1} 条")
    print("-"*70)
    
    complaint_count = 0
    for i, msg in enumerate(messages[1:], 2):
        result = classifier.classify(msg)
        if result.is_complaint:
            complaint_count += 1
        print(f"  [{i}] {msg.author}: {'🔥客诉' if result.is_complaint else '⚪非客诉'}"
              f" [{result.category or '-'}] {result.summary}")
    
    if result.is_complaint:
        complaint_count += 1
    total_complaints = sum(1 for c in [classifier.classify(m) for m in messages] if c.is_complaint)
    
    print(f"\n  总计: {len(messages)} 条, {total_complaints} 客诉 ({total_complaints/len(messages)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("✅ 诊断完成")
    print("="*70)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="google_play")
    p.add_argument("--target", required=True, help="包名")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--country", default="us", help="国家代码")
    p.add_argument("--lang", default="en", help="语言代码")
    p.add_argument("--all-regions", dest="global_mode", action="store_true",
                   help="🌍 全球模式")
    p.add_argument("--max-regions", type=int, default=6)
    args = p.parse_args()
    if args.global_mode:
        from src.sources import SourceFactory
        from src.models import Source as SourceEnum
        from src.config import load_config
        cfg = load_config()
        src = SourceFactory.create(SourceEnum(args.source), cfg.get("sources", {}).get(args.source, {}))
        if hasattr(src, 'fetch_global'):
            print(f"[2] 全球抓取 (max {args.max_regions} regions)\n")
            messages = src.fetch_global(target_id=args.target, limit=args.limit, max_regions=args.max_regions)
            print(f"  ✓ 抓到 {len(messages)} 条（去重后）")
            for m in messages:
                print(f"    [{m.author}] {m.content[:60]}")
            sys.exit(0)
    diagnose(args.source, args.target, args.limit, args.country, args.lang)
