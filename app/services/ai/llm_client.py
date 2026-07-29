"""百炼平台大模型调用封装（骨架占位）。"""

from app.core.config import get_settings


class LLMClient:
    """封装 DashScope / 百炼 API，屏蔽 SDK 细节。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def generate(self, question: str, chunks: list[dict]) -> dict:
        """
        根据问题与检索切块生成回答。

        返回纯数据：{"text": str, "sources": list}
        """
        _ = (question, chunks, self._settings.dashscope_api_key)
        return {
            "text": "（骨架占位）大模型尚未接入，请稍后配置 DASHSCOPE_API_KEY。",
            "sources": [],
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """文本向量化（骨架占位）。"""
        _ = texts
        return []


llm_client = LLMClient()
