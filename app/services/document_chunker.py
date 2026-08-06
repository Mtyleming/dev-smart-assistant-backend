"""文档文本切片：纯函数式切块，不调 AI、不写库。"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 按 token 计：块大小 / 重叠窗口
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

# 段落 > 句子 > 字符（兼顾中英文标点）
_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ".",
    "!",
    "?",
    "；",
    ";",
    " ",
    "",
]


@dataclass(frozen=True, slots=True)
class TextChunk:
    """内存切块：序号 + 原文。"""

    chunk_index: int
    content: str


def split_text(full_text: str | None) -> list[TextChunk]:
    """将全文按 RecursiveCharacterTextSplitter（tiktoken）切成块。

    Args:
        full_text: 文档解析后的全文；空或仅空白时返回空列表。

    Returns:
        切块列表，每项含 chunk_index（从 0 起）与 content。
    """
    text = (full_text or "").strip()
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        separators=_SEPARATORS,
    )
    pieces = splitter.split_text(text)
    return [
        TextChunk(chunk_index=index, content=piece)
        for index, piece in enumerate(pieces)
        if piece.strip()
    ]
