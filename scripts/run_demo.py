"""
快速演示脚本

无需参数，直接跑：
    python scripts/run_demo.py

会：
1. 抓取 5 条 Google Play 评论（用一个稳定存在的应用做演示）
2. 调 LLM 分类
3. 打印结果
4. 不写数据库

适合先验证 LLM 分类效果。
"""
import os
import sys
from pathlib import Path

# 让脚本能从项目根目录导入
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sources import GooglePlaySource
from src.classifier import LLMClassifier
from src.models import Source


def main():
    # 检查 API key
    if not os.getenv("MINIMAX_API_KEY"):
        print("❌ 请先设置 MINIMAX_API_KEY 环境变量")
        print("   编辑 .env 文件或: export MINIMAX_API_KEY=sk-xxxxx")
        return
    
    print("="*60)
    print("Game Ops Monitor - 快速演示")
    print("="*60)
    print()
    
    # 1. 抓取
    print("1️⃣  抓取 Google Play 评论...")
    gp = GooglePlaySource({"default_country": "us", "default_lang": "en"})
    messages = gp.fetch(
        target_id="com.android.chrome",  # 稳定存在的应用
        limit=5,
    )
    
    if not messages:
        print("❌ 抓取失败，请检查网络")
        return
    
    print(f"   ✓ 抓取 {len(messages)} 条")
    print()
    
    # 2. 分类
    print("2️⃣  LLM 分类...")
    classifier = LLMClassifier()
    classifications = classifier.classify_batch(messages)
    print(f"   ✓ 分类完成")
    print()
    
    # 3. 展示
    print("3️⃣  结果:")
    print("="*60)
    for i, (msg, cls) in enumerate(zip(messages, classifications), 1):
        print(f"\n[{i}] {msg.author} | {msg.rating}⭐ | {msg.timestamp}")
        print(f"    内容: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
        
        if cls.is_complaint:
            icon = "🔴" if cls.urgency >= 4 else "🟡" if cls.urgency >= 3 else "🟢"
            print(f"    ➜ 客诉 [{cls.category}] {icon} 紧急度 {cls.urgency}")
            print(f"    ➜ {cls.summary}")
            if cls.confidence:
                print(f"    ➜ 置信度: {cls.confidence:.2f}")
        else:
            print(f"    ➜ 非客诉")
    
    print("\n" + "="*60)
    complaint_count = sum(1 for c in classifications if c.is_complaint)
    print(f"总计: {len(messages)} 条消息, {complaint_count} 条客诉")
    print("="*60)


if __name__ == "__main__":
    main()
