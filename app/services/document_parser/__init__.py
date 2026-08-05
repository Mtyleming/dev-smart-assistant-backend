"""文档解析：按文件类型选用不同策略。"""

from app.services.document_parser.base import DocumentParseError
from app.services.document_parser.factory import parse_document

__all__ = ["DocumentParseError", "parse_document"]
