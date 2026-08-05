"""本地文件存储：知识库文档上传落盘。"""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

from app.core.config import settings

# 允许的扩展名 → 存库 file_type
ALLOWED_FILE_TYPES: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
}

_SAFE_NAME_RE = re.compile(r"[^\w.\u4e00-\u9fff-]+", re.UNICODE)


def resolve_file_type(filename: str | None) -> str | None:
    """根据文件名后缀解析 file_type；不支持则返回 None。"""
    if not filename or "." not in filename:
        return None
    suffix = Path(filename).suffix.lower()
    return ALLOWED_FILE_TYPES.get(suffix)


def safe_filename(filename: str | None) -> str:
    """生成相对安全的文件名片段，避免路径穿越。"""
    raw = Path(filename or "untitled").name
    cleaned = _SAFE_NAME_RE.sub("_", raw).strip("._") or "untitled"
    return cleaned[:200]


def build_relative_path(team_id: int, kb_id: int, filename: str | None) -> str:
    """生成相对存储路径：uploads/{team_id}/{kb_id}/{uuid}_{name}。"""
    name = safe_filename(filename)
    unique = f"{uuid.uuid4().hex}_{name}"
    return str(Path(settings.upload_dir) / str(team_id) / str(kb_id) / unique).replace(
        "\\", "/"
    )


def _write_bytes(abs_path: Path, content: bytes) -> int:
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    return len(content)


async def save_upload_file(relative_path: str, content: bytes) -> int:
    """将文件内容写入本地磁盘，返回字节数。"""
    abs_path = Path(relative_path)
    if not abs_path.is_absolute():
        abs_path = Path.cwd() / abs_path
    return await asyncio.to_thread(_write_bytes, abs_path, content)


def title_from_filename(filename: str | None) -> str:
    """用原始文件名作为文档标题（截断到 500）。"""
    name = Path(filename or "untitled").name.strip() or "untitled"
    return name[:500]
