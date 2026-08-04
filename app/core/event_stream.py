"""Server-Sent Events (SSE) 流式响应工具。"""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def format_sse_event(event: str | None, data: Any) -> str:
    """将事件名与数据格式化为 SSE 文本块。"""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    if event:
        return f"event: {event}\ndata: {payload}\n\n"
    return f"data: {payload}\n\n"


async def event_stream(
    events: AsyncIterator[tuple[str | None, Any]],
) -> AsyncIterator[str]:
    """将 (event, data) 异步迭代器转换为 SSE 文本流。"""
    async for event_name, data in events:
        yield format_sse_event(event_name, data)


def sse_response(event_generator: AsyncIterator[str]) -> StreamingResponse:
    """封装 SSE StreamingResponse。"""
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
