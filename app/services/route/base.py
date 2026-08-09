"""意图路由策略基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IntentRouteStrategy(ABC):
    """按意图执行对应业务逻辑的策略接口。

    当前为占位实现：各子类先返回固定结构，后续再接入真实 run 逻辑。
    """

    #: 意图标识，与意图识别结果 intent 字段一致
    intent: str
    #: LangGraph 节点名
    node_name: str

    @abstractmethod
    async def run(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
    ) -> dict:
        """执行该意图对应的业务逻辑。

        Args:
            message: 用户当前消息。
            conversation_id: 对话 ID。
            team_id: 团队 ID（知识库查询等场景需要）。
            kb_ids: 可选知识库 ID 列表；空表示团队下全部知识库。

        Returns:
            纯数据结果字典，至少包含 answer / intent / status 等字段。
        """
