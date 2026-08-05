"""文档解析策略单测。"""

from pathlib import Path

import pytest

from app.services.document_parser import DocumentParseError, parse_document
from app.services.document_parser.factory import get_parse_strategy
from app.services.document_parser.md_strategy import MarkdownParseStrategy
from app.services.document_parser.txt_strategy import TxtParseStrategy


def test_get_parse_strategy_unknown():
    with pytest.raises(DocumentParseError):
        get_parse_strategy("xlsx")


def test_txt_and_md_strategies_are_distinct():
    assert type(get_parse_strategy("txt")) is TxtParseStrategy
    assert type(get_parse_strategy("md")) is MarkdownParseStrategy


@pytest.mark.asyncio
async def test_parse_txt_file(tmp_path: Path):
    path = tmp_path / "hello.txt"
    path.write_text("你好，知识库", encoding="utf-8")
    text = await parse_document(str(path), "txt")
    assert "知识库" in text


@pytest.mark.asyncio
async def test_parse_md_file(tmp_path: Path):
    path = tmp_path / "readme.md"
    path.write_text("# 标题\n\n正文内容", encoding="utf-8")
    text = await parse_document(str(path), "md")
    assert "# 标题" in text
    assert "正文内容" in text
