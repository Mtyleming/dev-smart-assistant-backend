"""文本解码工具：兼容 UTF-8 / GBK 等常见编码。"""

from __future__ import annotations

from app.services.document_parser.base import DocumentParseError

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1")


def decode_bytes(raw: bytes) -> str:
    """将字节流解码为字符串。

    Args:
        raw: 文件原始字节。

    Returns:
        解码后的文本。

    Raises:
        DocumentParseError: 所有候选编码均失败时抛出。
    """
    if not raw:
        return ""
    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise DocumentParseError(
        f"无法识别文本编码: {last_error}"
    ) from last_error
