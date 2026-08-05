"""Markdown（.md / .markdown）解析策略。"""

from __future__ import annotations

from pathlib import Path

from app.services.document_parser.base import DocumentParseError, DocumentParseStrategy
from app.services.document_parser.encoding_utils import decode_bytes


class MarkdownParseStrategy(DocumentParseStrategy):
    """读取 Markdown 源文；当前保留原文（含标题/列表标记），便于后续切片。"""

    def extract_text(self, file_path: Path) -> str:
        """读取 Markdown 文件原文。

        Args:
            file_path: 本地 md 文件路径。

        Returns:
            Markdown 原文全文。

        Raises:
            DocumentParseError: 文件不存在或无法解码时抛出。
        """
        if not file_path.is_file():
            raise DocumentParseError("Markdown 文件不存在")
        try:
            raw = file_path.read_bytes()
        except OSError as exc:
            raise DocumentParseError(f"读取 Markdown 文件失败: {exc}") from exc
        # 与 txt 不同点：后续可在此剥离 YAML front matter、规范化换行等
        return decode_bytes(raw)
