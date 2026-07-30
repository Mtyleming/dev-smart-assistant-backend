"""认证相关请求与响应模型。"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """用户注册请求体。"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名，3-50 字符")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=1, description="密码，后端仅校验非空")


class LoginRequest(BaseModel):
    """用户登录请求体。"""

    number: str = Field(..., min_length=1, description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")


class RefreshRequest(BaseModel):
    """Token 续期请求体。"""

    refresh_token: str = Field(..., min_length=1, description="Refresh Token")


class UserBasicInfo(BaseModel):
    """用户基本信息（不含密码）。"""

    id: int
    username: str
    email: str
    team_id: int
    role: str
    is_active: bool


class MeData(BaseModel):
    """当前登录用户信息。"""

    id: int
    username: str
    email: str
    role: str
    team_id: int


class AuthData(BaseModel):
    """注册/登录成功后的认证数据。"""

    access_token: str
    refresh_token: str
    user: UserBasicInfo
