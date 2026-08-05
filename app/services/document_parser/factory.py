"""解析策略工厂：按 file_type 选择对应策略。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.document_parser.base import DocumentParseError, DocumentParseStrategy
from app.services.document_parser.docx_strategy import DocxParseStrategy
from app.services.document_parser.md_strategy import MarkdownParseStrategy
from app.services.document_parser.pdf_strategy import PdfParseStrategy
from app.services.document_parser.txt_strategy import TxtParseStrategy

_STRATEGIES: dict[str, DocumentParseStrategy] = {
    "pdf": PdfParseStrategy(),
    "docx": DocxParseStrategy(),
    "txt": TxtParseStrategy(),
    "md": MarkdownParseStrategy(),
}


def get_parse_strategy(file_type: str) -> DocumentParseStrategy:
    """按文件类型返回解析策略实例。

    Args:
        file_type: 存库的 file_type，如 pdf/docx/txt/md。

    Returns:
        对应的策略实现。

    Raises:
        DocumentParseError: 不支持的类型时抛出。
    """
    strategy = _STRATEGIES.get(file_type.lower())
    if strategy is None:
        raise DocumentParseError(f"不支持的文件类型: {file_type}")
    return strategy


def resolve_absolute_path(relative_or_abs: str) -> Path:
    """将相对存储路径解析为绝对路径。"""
    path = Path(relative_or_abs)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


async def parse_document(file_path: str, file_type: str) -> str:
    """异步包装：在线程池中执行同步解析，避免阻塞事件循环。

    Args:
        file_path: 相对或绝对本地路径。
        file_type: 文件类型 pdf/docx/txt/md。

    Returns:
        解析得到的全文。

    Raises:
        DocumentParseError: 类型不支持或解析失败时抛出。
    """
    strategy = get_parse_strategy(file_type)
    abs_path = resolve_absolute_path(file_path)
    return await asyncio.to_thread(strategy.extract_text, abs_path)
