"""
CLI 入口

命令：
- fetch: 抓取 + 分类 + 存储
- show:  查看客诉
- stats: 查看统计
- export: 导出 CSV/JSON
- sources: 列出可用的数据源和目标
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import load_config
from .models import MonitoredItem, Source
from .sources import SourceFactory
from .classifier import LLMClassifier
from .storage import SQLiteStore
from .diagnose import diagnose as run_diagnose

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_fetch(args):
    """抓取 + 分类 + 存储"""
    config = load_config(args.config)
    
    # 1. 创建数据源
    source_type = Source(args.source)
    sources_config = config.get("sources", {})
    source_config = sources_config.get(args.source, {})
    source = SourceFactory.create(source_type, source_config)
    
    # 2. 抓取
    logger.info(f"开始抓取 {args.target}...")
    if getattr(args, 'global_mode', False) and hasattr(source, 'fetch_global'):
        logger.info(f"🌍 全球模式: 最多抓 {args.max_regions} 个地区")
        messages = source.fetch_global(
            target_id=args.target,
            limit=args.limit,
            max_regions=args.max_regions,
        )
    else:
        messages = source.fetch(
            target_id=args.target,
            limit=args.limit,
            country=args.country,
            lang=args.lang,
        )
    if not messages:
        logger.warning("未抓取到任何消息")
        return
    logger.info(f"✓ 抓取 {len(messages)} 条消息")
    
    # 3. 分类
    if args.skip_classify:
        logger.info("跳过分类（--skip-classify）")
        return
    
    llm_config = config.get("llm", {})
    classifier = LLMClassifier(
        api_key=llm_config.get("api_key"),
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model", "MiniMax-M2.5"),
        temperature=llm_config.get("temperature", 0.1),
    )
    
    classifications = classifier.classify_batch(messages)
    
    # 4. 存储
    storage = SQLiteStore(config.get("storage", {}).get("db_path", "data/monitor.db"))
    
    items = [
        MonitoredItem(message=m, classification=c)
        for m, c in zip(messages, classifications)
    ]
    storage.save_batch(items)
    
    # 5. 统计
    complaint_count = sum(1 for c in classifications if c.is_complaint)
    storage.log_fetch(
        source=args.source,
        target_id=args.target,
        target_name=source_config.get("targets", [{}])[0].get("name") if source_config.get("targets") else None,
        fetched_count=len(messages),
        complaint_count=complaint_count,
        status="success",
    )
    
    # 6. 输出汇总
    print(f"\n{'='*60}")
    print(f"抓取: {len(messages)} 条")
    print(f"客诉: {complaint_count} 条 ({complaint_count/len(messages)*100:.1f}%)")
    print(f"{'='*60}")
    
    # 打印前 5 条客诉
    complaints = [
        (m, c) for m, c in zip(messages, classifications) if c.is_complaint
    ]
    if complaints:
        print(f"\n🔥 高优先客诉 (前 5 条):")
        for m, c in sorted(complaints, key=lambda x: -x[1].urgency)[:5]:
            print(f"  [{c.category or '?'}|紧急度{c.urgency}] {c.summary}")
            print(f"    作者: {m.author} | 时间: {m.timestamp}")
            print(f"    内容: {m.content[:100]}{'...' if len(m.content) > 100 else ''}")
            print()


def cmd_show(args):
    """查看客诉"""
    config = load_config(args.config)
    storage = SQLiteStore(config.get("storage", {}).get("db_path", "data/monitor.db"))
    
    rows = storage.query_complaints(
        source=args.source,
        category=args.category,
        min_urgency=args.min_urgency,
        only_complaints=not args.all,
        limit=args.limit,
    )
    
    if not rows:
        print("没有匹配的数据")
        return
    
    print(f"\n{'='*100}")
    print(f"{'时间':<19} {'来源':<10} {'类别':<12} {'紧急度':<6} {'摘要':<30} {'作者':<15}")
    print(f"{'='*100}")
    for row in rows:
        urgency_icon = "🔴" if row["urgency"] >= 4 else "🟡" if row["urgency"] >= 3 else "🟢"
        category = row["category"] or "-"
        ts = row["timestamp"][:19] if row["timestamp"] else "-"
        print(
            f"{ts:<19} {row['source']:<10} {category:<12} "
            f"{urgency_icon}{row['urgency']:<5} {row['summary'][:30]:<30} {row['author'][:15]:<15}"
        )
    
    print(f"\n共 {len(rows)} 条")
    print()
    print("查看详情: python -m src.cli detail <id>")
    print("导出:     python -m src.cli export --output report.csv")


def cmd_detail(args):
    """查看单条详情"""
    # 简单实现：从数据库查
    config = load_config(args.config)
    storage = SQLiteStore(config.get("storage", {}).get("db_path", "data/monitor.db"))
    
    with storage._get_conn() as conn:
        row = conn.execute("""
            SELECT m.*, c.is_complaint, c.category, c.urgency, c.summary, c.confidence, c.raw_response
            FROM messages m
            JOIN classifications c ON m.id = c.message_id
            WHERE m.id = ?
        """, (args.id,)).fetchone()
    
    if not row:
        print(f"未找到 ID={args.id}")
        return
    
    print(f"\n{'='*80}")
    print(f"ID: {row['id']}")
    print(f"来源: {row['source']} | 目标: {row['target_id']} ({row['target_name']})")
    print(f"作者: {row['author']}")
    print(f"时间: {row['timestamp']}")
    print(f"评分: {row['rating'] or '-'}")
    print(f"链接: {row['url']}")
    print(f"{'='*80}")
    print(f"分类: {row['category'] or '-'}")
    print(f"紧急度: {'🔴' if row['urgency'] >= 4 else '🟡' if row['urgency'] >= 3 else '🟢'} {row['urgency']}")
    print(f"摘要: {row['summary']}")
    print(f"置信度: {row['confidence']}")
    print(f"{'='*80}")
    print(f"原文:\n{row['content']}")
    print()


def cmd_stats(args):
    """统计信息"""
    config = load_config(args.config)
    storage = SQLiteStore(config.get("storage", {}).get("db_path", "data/monitor.db"))
    
    stats = storage.stats()
    
    print(f"\n{'='*60}")
    print(f"总消息数: {stats['total_messages']}")
    print(f"总客诉数: {stats['total_complaints']}")
    if stats['total_messages'] > 0:
        rate = stats['total_complaints'] / stats['total_messages'] * 100
        print(f"客诉率:   {rate:.1f}%")
    print(f"{'='*60}")
    
    if stats['by_category']:
        print("\n按类别:")
        for r in stats['by_category']:
            print(f"  {r['category']:<15} {r['count']:>5}")
    
    if stats['by_urgency']:
        print("\n按紧急度:")
        for r in stats['by_urgency']:
            icon = "🔴" if r['urgency'] >= 4 else "🟡" if r['urgency'] >= 3 else "🟢"
            print(f"  {icon} {r['urgency']}   {r['count']:>5}")
    
    if stats['by_source']:
        print("\n按数据源:")
        for r in stats['by_source']:
            print(f"  {r['source']:<15} {r['count']:>5}")
    print()


def cmd_export(args):
    """导出"""
    config = load_config(args.config)
    storage = SQLiteStore(config.get("storage", {}).get("db_path", "data/monitor.db"))
    
    rows = storage.query_complaints(
        source=args.source,
        category=args.category,
        min_urgency=args.min_urgency,
        only_complaints=not args.all,
        limit=10000,  # 导出全量
    )
    
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    if args.format == "json" or output.suffix == ".json":
        with open(output, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    else:
        # CSV
        if rows:
            with open(output, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
    
    print(f"✓ 已导出 {len(rows)} 条到 {output}")


def cmd_sources(args):
    """列出可用的数据源和目标"""
    config = load_config(args.config)
    sources = SourceFactory.create_from_config(config)
    
    if not sources:
        print("没有启用的数据源。请在 config.yaml 中启用。")
        return
    
    for source_type, source in sources.items():
        targets = source.list_targets()
        print(f"\n📡 {source_type.value}")
        print(f"   可用目标 ({len(targets)}):")
        for t in targets:
            status = "✓" if t.enabled else "✗"
            print(f"   {status} {t.id:<30} {t.name}")
    print()


def cmd_diagnose(args):
    """诊断命令"""
    run_diagnose(args.source, args.target, args.limit, args.country, args.lang)


def main():
    parser = argparse.ArgumentParser(
        description="Game Ops Monitor - 客诉自动监控与分类",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    sub = parser.add_subparsers(dest="command", help="子命令")
    
    # fetch
    p_fetch = sub.add_parser("fetch", help="抓取 + 分类 + 存储")
    p_fetch.add_argument("--source", required=True, choices=["google_play", "discord"], help="数据源")
    p_fetch.add_argument("--target", required=True, help="目标 ID（包名/频道 ID）")
    p_fetch.add_argument("--limit", type=int, default=50, help="抓取条数")
    p_fetch.add_argument("--country", default="cn", help="国家代码（Google Play）")
    p_fetch.add_argument("--lang", default="zh", help="语言代码")
    p_fetch.add_argument("--all-regions", dest="global_mode", action="store_true",
                          help="🌍 全球模式：遍历多地区抓取，合并去重（慢但全）")
    p_fetch.add_argument("--max-regions", type=int, default=6,
                          help="全球模式最多抓几个地区（默认 6）")
    p_fetch.add_argument("--skip-classify", action="store_true", help="跳过 LLM 分类")
    p_fetch.set_defaults(func=cmd_fetch)
    
    # show
    p_show = sub.add_parser("show", help="查看客诉")
    p_show.add_argument("--source", help="按数据源筛选")
    p_show.add_argument("--category", choices=["gameplay", "conflict", "tech", "monetization"], help="按类别")
    p_show.add_argument("--min-urgency", type=int, default=1, help="最低紧急度")
    p_show.add_argument("--all", action="store_true", help="包含非客诉")
    p_show.add_argument("--limit", type=int, default=50, help="显示条数")
    p_show.set_defaults(func=cmd_show)
    
    # detail
    p_detail = sub.add_parser("detail", help="查看单条详情")
    p_detail.add_argument("id", type=int, help="消息 ID")
    p_detail.set_defaults(func=cmd_detail)
    
    # stats
    p_stats = sub.add_parser("stats", help="统计信息")
    p_stats.set_defaults(func=cmd_stats)
    
    # export
    p_export = sub.add_parser("export", help="导出")
    p_export.add_argument("--output", required=True, help="输出文件")
    p_export.add_argument("--format", choices=["csv", "json"], help="格式（默认从扩展名推断）")
    p_export.add_argument("--source", help="按数据源筛选")
    p_export.add_argument("--category", choices=["gameplay", "conflict", "tech", "monetization"], help="按类别")
    p_export.add_argument("--min-urgency", type=int, default=1, help="最低紧急度")
    p_export.add_argument("--all", action="store_true", help="包含非客诉")
    p_export.set_defaults(func=cmd_export)
    
    # sources
    p_sources = sub.add_parser("sources", help="列出可用数据源和目标")
    p_sources.set_defaults(func=cmd_sources)
    
    # diagnose
    p_diag = sub.add_parser("diagnose", help="🔍 诊断：详细输出抓取+分类每一步，定位问题")
    p_diag.add_argument("--source", default="google_play", help="数据源")
    p_diag.add_argument("--target", required=True, help="目标包名")
    p_diag.add_argument("--limit", type=int, default=3, help="抓取条数")
    p_diag.add_argument("--country", default="us", help="国家代码")
    p_diag.add_argument("--lang", default="en", help="语言代码")
    p_diag.set_defaults(func=cmd_diagnose)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        args.func(args)
    except Exception as e:
        logger.exception(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
