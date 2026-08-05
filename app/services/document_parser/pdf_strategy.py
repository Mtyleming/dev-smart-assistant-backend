"""PDF 解析策略。"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.services.document_parser.base import DocumentParseError, DocumentParseStrategy


class PdfParseStrategy(DocumentParseStrategy):
    """按页提取 PDF 文本并拼接为全文。"""

    def extract_text(self, file_path: Path) -> str:
        """从 PDF 提取文本。

        Args:
            file_path: 本地 pdf 文件路径。

        Returns:
            各页文本用换行拼接后的全文。

        Raises:
            DocumentParseError: 文件损坏或无法读取时抛出。
        """
        if not file_path.is_file():
            raise DocumentParseError("PDF 文件不存在")
        try:
            reader = PdfReader(str(file_path))
            if getattr(reader, "is_encrypted", False):
                # 尝试空密码；失败则明确报错
                try:
                    unlocked = reader.decrypt("")
                except Exception as exc:  # noqa: BLE001
                    raise DocumentParseError("PDF 已加密，无法解析") from exc
                if unlocked == 0:
                    raise DocumentParseError("PDF 已加密，无法解析")

            parts: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    parts.append(text)
            return "\n".join(parts).strip()
        except DocumentParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DocumentParseError(f"PDF 解析失败: {exc}") from exc
