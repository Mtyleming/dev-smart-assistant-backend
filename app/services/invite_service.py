"""邀请入团与审批业务逻辑。"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, ConflictError, ForbiddenError, NotFoundError
from app.models.base_models import TeamMemberRole
from app.repositories.cache_repo import (
    INVITE_CODE_TTL_SECONDS,
    cache_repo,
)
from app.repositories.team_member_repo import team_member_repo
from app.repositories.team_repo import team_repo
from app.repositories.user_repo import user_repo
from app.schemas.invitation import (
    ApproveJoinRequest,
    InviteCodeData,
    JoinRequestData,
    JoinTeamData,
    JoinTeamRequest,
)


class InviteService:
    """邀请码生成、入团申请与审批。"""

    async def create_invite_code(
        self,
        db: AsyncSession,
        redis: Redis | None,
        team_id: int,
        user_id: str,
    ) -> InviteCodeData:
        """生成 7 天有效的一次性邀请码（路由层已校验 admin）。"""
        _ = user_id
        if redis is None:
            raise AppException(
                code=50001, message="服务暂不可用，请稍后重试", status_code=503
            )

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        invite_code = secrets.token_urlsafe(12)
        created_at = datetime.now(timezone.utc).isoformat()
        await cache_repo.set_invite_code(
            redis,
            invite_code,
            {
                "team_id": str(team_id),
                "inviter_id": user_id,
                "created_at": created_at,
            },
        )

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=INVITE_CODE_TTL_SECONDS
        )
        return InviteCodeData(
            invite_code=invite_code,
            expires_at=expires_at,
            team_id=team_id,
        )

    async def apply_to_join(
        self,
        db: AsyncSession,
        redis: Redis | None,
        user_id: str,
        payload: JoinTeamRequest,
    ) -> JoinTeamData:
        """使用邀请码申请加入团队，邀请码一次性失效。"""
        if redis is None:
            raise AppException(
                code=50001, message="服务暂不可用，请稍后重试", status_code=503
            )

        invite_data = await cache_repo.get_invite_code(redis, payload.invite_code)
        if not invite_data:
            raise NotFoundError("邀请码无效或已过期")

        team_id = int(invite_data["team_id"])
        team = await team_repo.get_by_id(db, team_id)
        if not team or team.is_delete:
            raise NotFoundError("邀请码无效或已过期")

        user = await user_repo.get_by_id(db, int(user_id))
        if not user:
            raise NotFoundError("用户不存在")

        existing = await team_member_repo.get_membership(db, team_id, int(user_id))
        if existing:
            raise ConflictError("您已是该团队成员")

        pending_ids = await cache_repo.list_team_pending_request_ids(redis, team_id)
        for request_id in pending_ids:
            request_data = await cache_repo.get_join_request(redis, request_id)
            if (
                request_data
                and request_data.get("status") == "pending"
                and request_data.get("user_id") == user_id
            ):
                raise ConflictError("您已有待审批的入团申请")

        request_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        await cache_repo.create_join_request(
            redis,
            request_id,
            {
                "user_id": user_id,
                "username": user.username,
                "team_id": str(team_id),
                "invite_code": payload.invite_code,
                "status": "pending",
                "created_at": created_at,
            },
        )
        await cache_repo.add_team_pending_request(redis, team_id, request_id)
        await cache_repo.delete_invite_code(redis, payload.invite_code)

        return JoinTeamData(
            request_id=request_id,
            team_id=team_id,
            team_name=team.name,
            status="pending",
        )

    async def list_join_requests(
        self,
        db: AsyncSession,
        redis: Redis | None,
        team_id: int,
        user_id: str,
    ) -> list[JoinRequestData]:
        """列出团队待审批入团申请（路由层已校验 admin）。"""
        _ = user_id
        if redis is None:
            raise AppException(
                code=50001, message="服务暂不可用，请稍后重试", status_code=503
            )

        request_ids = await cache_repo.list_team_pending_request_ids(redis, team_id)
        results: list[JoinRequestData] = []
        for request_id in request_ids:
            data = await cache_repo.get_join_request(redis, request_id)
            if not data or data.get("status") != "pending":
                continue
            results.append(
                JoinRequestData(
                    request_id=request_id,
                    user_id=int(data["user_id"]),
                    username=data["username"],
                    created_at=data["created_at"],
                    status=data["status"],
                )
            )
        return results

    async def approve_join_request(
        self,
        db: AsyncSession,
        redis: Redis | None,
        team_id: int,
        request_id: str,
        user_id: str,
        payload: ApproveJoinRequest,
    ) -> None:
        """审批通过入团申请，写入团队成员并清理 Redis（路由层已校验 admin）。"""
        _ = user_id
        if redis is None:
            raise AppException(
                code=50001, message="服务暂不可用，请稍后重试", status_code=503
            )

        data = await self._get_pending_request(redis, team_id, request_id)
        applicant_id = int(data["user_id"])

        existing = await team_member_repo.get_membership(db, team_id, applicant_id)
        if existing:
            await self._cleanup_join_request(redis, team_id, request_id)
            raise ConflictError("用户已是团队成员")

        if payload.role == TeamMemberRole.admin:
            admin_count = await team_member_repo.count_admins_by_team(db, team_id)
            if admin_count > 0:
                raise ConflictError("团队已有管理员，请通过转让方式变更")

        await team_member_repo.create(
            db,
            team_id=team_id,
            user_id=applicant_id,
            role=payload.role,
        )
        await db.commit()
        await self._cleanup_join_request(redis, team_id, request_id)

    async def reject_join_request(
        self,
        db: AsyncSession,
        redis: Redis | None,
        team_id: int,
        request_id: str,
        user_id: str,
    ) -> None:
        """拒绝入团申请，仅清理 Redis（路由层已校验 admin）。"""
        _ = user_id
        if redis is None:
            raise AppException(
                code=50001, message="服务暂不可用，请稍后重试", status_code=503
            )

        await self._get_pending_request(redis, team_id, request_id)
        await self._cleanup_join_request(redis, team_id, request_id)

    async def _get_pending_request(
        self, redis: Redis, team_id: int, request_id: str
    ) -> dict[str, str]:
        data = await cache_repo.get_join_request(redis, request_id)
        if not data or data.get("status") != "pending":
            raise NotFoundError("审批记录不存在")
        if int(data.get("team_id", 0)) != team_id:
            raise ForbiddenError("无权操作该审批")
        return data

    async def _cleanup_join_request(
        self, redis: Redis, team_id: int, request_id: str
    ) -> None:
        await cache_repo.remove_team_pending_request(redis, team_id, request_id)
        await cache_repo.delete_join_request(redis, request_id)


invite_service = InviteService()
