"""意图识别手工测试脚本。

用法（在项目根目录、已激活 .venv）：

    python test/test_intent_classify.py

可选：自己输入一句话再测一遍

    python test/test_intent_classify.py --ask
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 保证从任意工作目录运行都能找到 app 包，并切到项目根
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.config import settings
from app.services.ai.intent_service import classify_intent
from app.services.route import get_route_strategy, resolve_node_name


# 四类意图各准备 1～2 句典型话，方便对照结果
SAMPLE_CASES: list[tuple[str, str]] = [
    ("knowledge_query", "帮我查一下团队知识库里 FastAPI 的鉴权规范怎么写"),
    ("knowledge_query", "我们内部的编码规范对日志格式有什么要求？"),
    ("general_qa", "什么是 HTTP 状态码 503？"),
    ("general_qa", "解释一下什么是微服务"),
    ("code_request", "帮我写一个 Python 快速排序函数"),
    ("code_request", "请审查这段代码有没有安全问题：password = request.args.get('pwd')"),
    ("doc_generation", "根据用户登录功能帮我生成一份接口设计文档"),
    ("doc_generation", "请生成一份知识库上传接口的 README 说明"),
]


class MemoryRedis:
    """Redis 不可用时的内存假客户端，只实现 get/set，方便本地测意图。"""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        _ = ex
        self._store[key] = value
        return True


async def _get_redis_or_memory():
    """优先用真 Redis；连不上就用内存假客户端。"""
    try:
        from app.core.redis import redis_client

        await redis_client.ping()
        print("[缓存] 已连接 Redis")
        return redis_client, True
    except Exception as exc:
        print(f"[缓存] Redis 不可用（{exc}），改用内存缓存")
        return MemoryRedis(), False


async def run_one(
    redis,
    message: str,
    *,
    expected: str | None = None,
    conversation_id: int = 999001,
    history: list[dict] | None = None,
) -> dict:
    """跑一次意图识别并打印结果。"""
    result = await classify_intent(
        message=message,
        conversation_id=conversation_id,
        history=history or [],
        redis_client=redis,
    )
    intent = result.get("intent")
    confidence = result.get("confidence")
    node = resolve_node_name(intent)
    strategy = get_route_strategy(intent)

    mark = ""
    if expected:
        mark = " [OK]" if intent == expected else f" [FAIL] expected={expected}"

    print("-" * 60)
    print(f"消息: {message}")
    print(f"意图: {intent}  置信度: {confidence}{mark}")
    print(f"节点: {node}  策略: {strategy.__class__.__name__}")
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="测试意图识别是否正常")
    parser.add_argument(
        "--ask",
        action="store_true",
        help="跑完样例后，允许自己输入一句话再测",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("意图识别测试")
    print("=" * 60)
    print(f"工作目录: {Path.cwd()}")
    print(f"模型: {settings.llm_model}")
    print(f"Key 已配置: {'是' if settings.llm_api_key else '否（将降级为 general_qa）'}")
    if settings.llm_api_key:
        print(f"Key 长度: {len(settings.llm_api_key)}")
    if not settings.llm_api_key:
        print("请先在项目根目录 .env 填写 DASHSCOPE_API_KEY 再测真实识别效果。")

    redis, _ = await _get_redis_or_memory()

    ok = 0
    total = len(SAMPLE_CASES)
    for expected, message in SAMPLE_CASES:
        result = await run_one(redis, message, expected=expected)
        if result.get("intent") == expected:
            ok += 1

    print("=" * 60)
    print(f"样例命中: {ok}/{total}")
    print("说明：大模型偶发会判错，命中多数即可；若几乎全错请检查 Key/模型。")
    print("=" * 60)

    if args.ask:
        print("\n输入一句话测试（直接回车结束）：")
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                break
            await run_one(redis, text)


if __name__ == "__main__":
    asyncio.run(main())
