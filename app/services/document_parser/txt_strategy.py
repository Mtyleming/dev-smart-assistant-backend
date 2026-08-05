"""纯文本（.txt）解析策略。"""

from __future__ import annotations

from pathlib import Path

from app.services.document_parser.base import DocumentParseError, DocumentParseStrategy
from app.services.document_parser.encoding_utils import decode_bytes


class TxtParseStrategy(DocumentParseStrategy):
    """按常见编码读取 .txt 全文。"""

    def extract_text(self, file_path: Path) -> str:
        """读取 txt 文件并解码为字符串。

        Args:
            file_path: 本地 txt 文件路径。

        Returns:
            全文文本。

        Raises:
            DocumentParseError: 文件不存在或无法解码时抛出。
        """
        if not file_path.is_file():
            raise DocumentParseError("文本文件不存在")
        try:
            raw = file_path.read_bytes()
        except OSError as exc:
            raise DocumentParseError(f"读取文本文件失败: {exc}") from exc
        return decode_bytes(raw)
