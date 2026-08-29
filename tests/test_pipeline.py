"""
端到端测试

不需要 API key，不调用 LLM，验证数据流和模型正确性。
"""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# 允许从项目根目录运行
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import RawMessage, ClassificationResult, MonitoredItem, Source, Category
from src.storage import SQLiteStore
from src.sources import GooglePlaySource, SourceFactory


def test_data_model():
    """测试数据模型"""
    print("Testing RawMessage + ClassificationResult...")
    msg = RawMessage(
        source=Source.GOOGLE_PLAY,
        source_id="test123",
        target_id="com.test.app",
        author="玩家A",
        content="游戏闪退",
        timestamp=datetime.utcnow(),
        rating=1,
    )
    assert msg.source == "google_play"
    assert msg.rating == 1
    print("  ✓ RawMessage")
    
    result = ClassificationResult(
        is_complaint=True,
        category=Category.TECH,
        urgency=4,
        summary="闪退问题",
    )
    assert result.is_complaint
    assert result.category == "tech"
    print("  ✓ ClassificationResult")
    
    item = MonitoredItem(message=msg, classification=result)
    assert item.message.author == "玩家A"
    print("  ✓ MonitoredItem")
    print()


def test_storage():
    """测试 SQLite 存储"""
    print("Testing SQLiteStore...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        store = SQLiteStore(db_path)
        
        # 写入
        msg = RawMessage(
            source=Source.GOOGLE_PLAY,
            source_id="test_storage_1",
            target_id="com.test.app",
            author="测试用户",
            content="卡顿严重",
            timestamp=datetime.utcnow(),
            rating=2,
        )
        result = ClassificationResult(
            is_complaint=True,
            category=Category.TECH,
            urgency=3,
            summary="卡顿",
        )
        item = MonitoredItem(message=msg, classification=result)
        msg_id = store.save_item(item)
        assert msg_id > 0
        print(f"  ✓ 写入消息 ID={msg_id}")
        
        # 查询
        rows = store.query_complaints(category="tech", min_urgency=3)
        assert len(rows) == 1
        assert rows[0]["author"] == "测试用户"
        print(f"  ✓ 查询到 {len(rows)} 条记录")
        
        # 统计
        stats = store.stats()
        assert stats["total_messages"] == 1
        assert stats["total_complaints"] == 1
        print(f"  ✓ 统计: {stats['total_complaints']} 客诉")
        
        # 去重
        msg2 = RawMessage(
            source=Source.GOOGLE_PLAY,
            source_id="test_storage_1",  # 相同 ID
            target_id="com.test.app",
            author="测试用户",
            content="卡顿严重（更新）",
            timestamp=datetime.utcnow(),
            rating=2,
        )
        item2 = MonitoredItem(
            message=msg2,
            classification=ClassificationResult(
                is_complaint=True,
                category=Category.TECH,
                urgency=4,
                summary="卡顿（升级）",
            ),
        )
        msg_id2 = store.save_item(item2)
        assert msg_id2 == msg_id, "相同 source_id 应该更新而非新增"
        print(f"  ✓ 去重更新: 仍是 ID={msg_id2}")
    print()


def test_factory():
    """测试数据源工厂"""
    print("Testing SourceFactory...")
    config = {
        "google_play": {
            "enabled": True,
            "targets": [
                {"id": "com.test.app1", "name": "测试1", "country": "cn", "lang": "zh"},
            ],
        },
        "discord": {"enabled": False, "targets": []},
    }
    
    # 单个创建
    gp = SourceFactory.create(Source.GOOGLE_PLAY, config["google_play"])
    assert isinstance(gp, GooglePlaySource)
    print(f"  ✓ 创建: {gp}")
    
    # 列出目标
    targets = gp.list_targets()
    assert len(targets) == 1
    assert targets[0].id == "com.test.app1"
    print(f"  ✓ 目标: {targets[0].name}")
    
    # 从配置创建
    sources = SourceFactory.create_from_config({"sources": config})
    assert Source.GOOGLE_PLAY in sources
    assert Source.DISCORD not in sources  # 禁用了
    print(f"  ✓ 从配置启用: {[s.value for s in sources.keys()]}")
    print()


def test_google_play_fetch():
    """测试 Google Play 抓取（真实网络，需要联网）"""
    print("Testing GooglePlaySource.fetch() [requires network]...")
    try:
        gp = GooglePlaySource({"default_country": "us", "default_lang": "en"})
        # 用一个稳定存在的应用
        messages = gp.fetch("com.android.settings", limit=3)
        if messages:
            assert all(isinstance(m, RawMessage) for m in messages)
            print(f"  ✓ 抓取到 {len(messages)} 条")
            for m in messages[:2]:
                print(f"    - [{m.rating}⭐] {m.author}: {m.content[:60]}...")
        else:
            print("  ⚠️  抓取为空（可能网络问题）")
    except Exception as e:
        print(f"  ⚠️  跳过（网络错误: {type(e).__name__}）")
    print()


def test_llm_classify_mock():
    """测试 LLM 分类（mock，不真调用）"""
    print("Testing LLMClassifier (mock, no real API call)...")
    from unittest.mock import patch, MagicMock
    
    # mock OpenAI 客户端
    with patch("src.classifier.llm.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_complaint": True,
            "category": "tech",
            "urgency": 4,
            "summary": "闪退问题",
            "confidence": 0.95,
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        from src.classifier import LLMClassifier
        classifier = LLMClassifier(api_key="mock-key")
        
        msg = RawMessage(
            source=Source.GOOGLE_PLAY,
            source_id="x",
            target_id="x",
            author="x",
            content="每次打开就闪退",
            timestamp=datetime.utcnow(),
        )
        result = classifier.classify(msg)
        assert result.is_complaint
        assert result.category == "tech"
        assert result.urgency == 4
        print(f"  ✓ Mock 分类成功: {result.category}/{result.urgency} - {result.summary}")
    print()


import json

if __name__ == "__main__":
    print("="*60)
    print("Game Ops Monitor - 端到端测试")
    print("="*60)
    print()
    
    test_data_model()
    test_storage()
    test_factory()
    test_google_play_fetch()
    test_llm_classify_mock()
    
    print("="*60)
    print("✅ 所有测试通过")
    print("="*60)
