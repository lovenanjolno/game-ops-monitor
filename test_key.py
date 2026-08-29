"""测试 minimax API key 是否有效"""
import os
from dotenv import load_dotenv  # ← 关键：先加载 .env
from openai import OpenAI

# 1. 加载 .env 文件
load_dotenv()

# 2. 从环境变量读
API_KEY = os.getenv("MINIMAX_API_KEY")
BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")

if not API_KEY:
    print("❌ MINIMAX_API_KEY 未设置！")
    print("   检查：")
    print("   1. 项目根目录有 .env 文件吗？")
    print("   2. .env 里写了 MINIMAX_API_KEY=... 吗？")
    print("   3. 或者在 PowerShell 里 $env:MINIMAX_API_KEY 设了吗？")
    exit(1)

print(f"Key starts with: {API_KEY[:12]}...")
print(f"Key length: {len(API_KEY)}")
print(f"Base URL: {BASE_URL}")
print(f"Model: {MODEL}")
print()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

try:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "hi"}],
        timeout=30,
    )
    print(f"Status: 200 OK")
    print(f"Reply: {r.choices[0].message.content}")
except Exception as e:
    print(f"Exception type: {type(e).__name__}")
    print(f"Error: {e}")
