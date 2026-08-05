"""文档解析策略基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentParseError(Exception):
    """文档解析失败。"""

    def __init__(self, message: str = "文档解析失败"):
        self.message = message
        super().__init__(message)


class DocumentParseStrategy(ABC):
    """解析策略接口：不同格式各自实现 extract_text。"""

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """从本地文件提取纯文本全文。

        Args:
            file_path: 已落盘的文档绝对路径。

        Returns:
            解析得到的全文（可为空字符串以外的空白需调用方自行判断）。

        Raises:
            DocumentParseError: 文件损坏、无法解码或库解析失败时抛出。
        """
