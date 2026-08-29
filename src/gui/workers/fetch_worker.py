"""
异步抓取 Worker

把"抓取 + 分类 + 入库"放到后台线程，不阻塞 UI。
通过信号（Signal）把进度和结果推回主线程。
"""
from __future__ import annotations

import logging
import time
import sys
from pathlib import Path
from typing import Optional

# 确保能从项目根目录 import
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.config import load_config
from src.models import MonitoredItem, Source
from src.sources import SourceFactory
from src.classifier import LLMClassifier
from src.storage import SQLiteStore

logger = logging.getLogger(__name__)


class FetchWorker(QObject):
    """
    抓取 Worker
    
    信号：
    - started: 开始
    - progress(int, str): 进度 (0-100, 描述)
    - finished(dict): 完成 (统计信息)
    - error(str): 错误
    """
    
    started = pyqtSignal()
    progress = pyqtSignal(int, str)  # percent, message
    finished = pyqtSignal(dict)      # stats
    error = pyqtSignal(str)
    
    def __init__(
        self,
        source_type: str,
        target_id: str,
        target_name: Optional[str] = None,
        limit: int = 50,
        country: str = "cn",
        lang: str = "zh",
        days: Optional[int] = None,
        global_mode: bool = False,
        max_regions: int = 6,
        skip_classify: bool = False,
    ):
        super().__init__()
        self.source_type = source_type
        self.target_id = target_id
        self.target_name = target_name
        self.limit = limit
        self.country = country
        self.lang = lang
        self.days = days
        self.global_mode = global_mode
        self.max_regions = max_regions
        self.skip_classify = skip_classify
        self._cancelled = False
    
    def cancel(self):
        """请求取消（尽力而为，已经发出的请求无法撤回）"""
        self._cancelled = True
    
    def run(self):
        """Worker 入口（在 QThread 中执行）"""
        try:
            self.started.emit()
            self.progress.emit(0, "加载配置...")
            
            config = load_config()
            
            # ---- 1. 创建数据源 ----
            self.progress.emit(10, f"准备 {self.source_type} 数据源...")
            sources_config = config.get("sources", {})
            source_config = sources_config.get(self.source_type, {})
            source = SourceFactory.create(Source(self.source_type), source_config)
            
            # ---- 2. 抓取 ----
            if self._cancelled:
                return
            
            days_text = f" / 最近 {self.days} 天" if self.days else ""
            
            t0 = time.time()
            if self.global_mode and hasattr(source, 'fetch_global'):
                self.progress.emit(20, f"🌍 全球抓取 {self.target_id} (最多 {self.max_regions} 地区)...")
                messages = source.fetch_global(
                    target_id=self.target_id,
                    limit=self.limit,
                    max_regions=self.max_regions,
                    days=self.days,
                )
            else:
                self.progress.emit(20, f"抓取 {self.target_id} ({self.limit} 条{days_text})...")
                messages = source.fetch(
                    target_id=self.target_id,
                    limit=self.limit,
                    country=self.country,
                    lang=self.lang,
                    days=self.days,
                )
            fetch_time = time.time() - t0
            
            if not messages:
                self.error.emit("未抓取到任何评论（包名错误、无评论或网络问题）")
                return
            
            self.progress.emit(50, f"✓ 抓取 {len(messages)} 条 (耗时 {fetch_time:.1f}s)")
            
            # ---- 3. 分类 ----
            classifications = []
            if not self.skip_classify:
                if self._cancelled:
                    return
                self.progress.emit(55, "初始化 LLM 分类器...")
                
                llm_config = config.get("llm", {})
                try:
                    classifier = LLMClassifier(
                        api_key=llm_config.get("api_key"),
                        base_url=llm_config.get("base_url"),
                        model=llm_config.get("model", "MiniMax-M2.5"),
                        temperature=llm_config.get("temperature", 0.1),
                    )
                except Exception as e:
                    self.error.emit(f"LLM 初始化失败: {e}")
                    return
                
                self.progress.emit(60, f"分类 {len(messages)} 条消息...")

                classify_failed = 0
                first_failure_reason = None
                for i, msg in enumerate(messages):
                    if self._cancelled:
                        return
                    cls = classifier.classify(msg)
                    # 检测分类是否真的失败
                    if cls.raw_response and ("分类失败" in cls.summary or
                                              cls.summary.startswith("[分类失败")):
                        classify_failed += 1
                        if first_failure_reason is None:
                            first_failure_reason = cls.raw_response[:200]
                    classifications.append(cls)
                    # 每 10% 更新一次
                    if (i + 1) % max(1, len(messages) // 10) == 0:
                        pct = 60 + int((i + 1) / len(messages) * 30)
                        self.progress.emit(
                            pct, f"分类中... {i + 1}/{len(messages)}"
                        )

                if classify_failed > 0:
                    self.progress.emit(90, f"⚠️ 分类完成: {classify_failed} 条失败")
                else:
                    self.progress.emit(90, f"✓ 分类完成")
            
            # ---- 4. 入库 ----
            if self._cancelled:
                return
            self.progress.emit(92, "写入数据库...")
            
            storage = SQLiteStore(
                config.get("storage", {}).get("db_path", "data/monitor.db")
            )
            
            items = [
                MonitoredItem(message=m, classification=c)
                for m, c in zip(messages, classifications)
            ]
            storage.save_batch(items)
            
            complaint_count = sum(1 for c in classifications if c.is_complaint)
            storage.log_fetch(
                source=self.source_type,
                target_id=self.target_id,
                target_name=self.target_name,
                fetched_count=len(messages),
                complaint_count=complaint_count,
                status="success",
            )
            
            # ---- 完成 ----
            self.progress.emit(100, "✓ 完成")
            self.finished.emit({
                "fetched": len(messages),
                "complaints": complaint_count,
                "classify_failed": classify_failed,
                "first_failure_reason": first_failure_reason if 'first_failure_reason' in dir() else None,
                "fetch_time": fetch_time,
                "target_id": self.target_id,
            })
        
        except Exception as e:
            logger.exception("Worker error")
            self.error.emit(f"{type(e).__name__}: {e}")


def run_fetch_in_thread(worker: FetchWorker) -> QThread:
    """
    在 QThread 中运行 Worker
    
    用法：
        worker = FetchWorker(...)
        thread = run_fetch_in_thread(worker)
        thread.start()
    """
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    return thread
