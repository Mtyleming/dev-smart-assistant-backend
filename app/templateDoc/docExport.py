"""文档导出：Markdown → HTML / PDF。"""

from __future__ import annotations

import html
import logging
import os
from io import BytesIO
from pathlib import Path

from app.core.exceptions import AppException, UnsupportedFormatError

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ("markdown", "html", "pdf")


def _cjk_font_path() -> str | None:
    """查找本机可用的中文字体，供 PDF 渲染使用。"""
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windir / "Fonts" / "simhei.ttf",
        windir / "Fonts" / "simkai.ttf",
        windir / "Fonts" / "msyh.ttf",
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _build_html(content: str, title: str) -> str:
    """把 Markdown 转成带基础样式的完整 HTML 页面。"""
    import markdown

    safe_title = html.escape(title or "文档")
    html_body = markdown.markdown(
        content or "",
        extensions=["tables", "fenced_code", "nl2br"],
    )
    font_face = ""
    font_family = "sans-serif"
    font_path = _cjk_font_path()
    if font_path:
        href = Path(font_path).as_uri()
        font_face = (
            f"@font-face{{font-family:DocCJK;src:url('{href}')}}"
        )
        font_family = "DocCJK, sans-serif"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{safe_title}</title>
<style>
{font_face}
body{{font-family:{font_family};max-width:800px;margin:40px auto;padding:0 20px;line-height:1.6;color:#222}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
pre{{background:#f6f8fa;padding:12px;overflow:auto}}
code{{font-family:Consolas,monospace}}
blockquote{{border-left:4px solid #ddd;margin:0;padding:0 12px;color:#555}}
</style>
</head>
<body>{html_body}</body>
</html>"""


def _html_to_pdf(html_text: str) -> bytes:
    """优先 WeasyPrint；Windows 无 GTK 时回退 xhtml2pdf。"""
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_text).write_pdf()
        if pdf_bytes:
            return pdf_bytes
    except Exception as exc:
        logger.warning("WeasyPrint 不可用，改用 xhtml2pdf：%s", exc)

    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        logger.error("xhtml2pdf 未安装，无法导出 PDF")
        raise AppException(
            code=50305,
            message="PDF 导出依赖缺失，请安装 markdown 与 xhtml2pdf（或 weasyprint）",
            status_code=503,
        ) from exc

    result = BytesIO()
    status = pisa.CreatePDF(src=html_text, dest=result, encoding="utf-8")
    if status.err:
        logger.error("xhtml2pdf 渲染失败 err=%s", status.err)
        raise AppException(
            code=50306,
            message="PDF 导出失败，请改用 HTML 格式或检查本机中文字体",
            status_code=503,
        )
    return result.getvalue()


class DocExporter:
    """把 Markdown 正文导出为指定格式的字节内容。"""

    async def export(self, content: str, format: str, filename: str) -> bytes:
        """按 format 导出；format 仅支持 markdown / html / pdf。"""
        fmt = (format or "").strip().lower()
        if fmt == "markdown" or fmt == "md":
            return (content or "").encode("utf-8")
        if fmt == "html":
            return _build_html(content, filename).encode("utf-8")
        if fmt == "pdf":
            html_text = _build_html(content, filename)
            return _html_to_pdf(html_text)
        raise UnsupportedFormatError(
            f"不支持的导出格式：{format}，仅支持 markdown/html/pdf"
        )


doc_exporter = DocExporter()
