"""文档生成业务逻辑。"""


class DocGeneratorService:
    """根据模板/需求生成文档（骨架占位）。"""

    async def generate(self, title: str, outline: list[str] | None = None) -> dict:
        """生成文档草稿。"""
        _ = outline
        return {
            "title": title,
            "content": f"（骨架占位）文档《{title}》尚未接入生成链路。",
        }


doc_generator_service = DocGeneratorService()
