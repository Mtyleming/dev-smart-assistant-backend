# 开发智能助手 · 后端工程

> 工程名：`dev-smart-assistant-backend`  
> 本地路径：`D:\agentProject\dev-smart-assistant-backend`  
> 技术依据：`04a-后端技术选型.md`  
> GitHub：https://github.com/Mtyleming/dev-smart-assistant-backend

这是「开发智能助手」的后端项目。它负责：

1. **对外提供 API**：用户、团队、知识库、对话、智能问答、代码辅助、文档生成  
2. **对接 AI 能力**：百炼大模型、RAG 检索、LangGraph Agent（封装在服务层，路由层不直接调用）  
3. **读写业务数据**：MySQL（结构化数据）、Milvus（向量）、Redis（缓存）

即使数据库还没配好，你也可以先启动服务，打开 `/docs` 看接口文档，并调用各模块的 `/status` 确认路由已挂载。

---

## 一、技术栈（一句话版）

| 用途 | 技术 | 作用 |
|------|------|------|
| 运行语言 | Python 3.12+ | 写全部后端逻辑 |
| Web 框架 | FastAPI 0.137.x | 异步 HTTP API + 自动文档 |
| ORM | SQLAlchemy 2.0.x | 异步访问 MySQL |
| 数据库 | MySQL 8.0 | 存用户、团队、知识库、对话等 |
| API 前缀 | `/api/v1` | 全部业务接口统一前缀 |
| 架构 | 路由 → 服务 → 数据访问 | 三层分工，互不越界 |

---

## 二、怎么启动（最重要）

### 1. 进入项目目录

```bash
cd D:\agentProject\dev-smart-assistant-backend
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
copy .env.example .env
```

用记事本打开 `.env`，按你本机 MySQL / Redis 改账号密码（暂时不配也能先看文档和 `/health`）。

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 打开接口文档

浏览器访问：

- Swagger UI：http://127.0.0.1:8000/docs  
- ReDoc：http://127.0.0.1:8000/redoc  
- 健康检查：http://127.0.0.1:8000/health  

---

## 三、目录结构（对照选型文档）

```
app/
├── main.py                  # FastAPI 入口，挂载全部路由
├── dependencies.py          # 依赖注入：数据库会话、当前用户
├── core/                    # 配置、数据库、业务异常
├── routers/                 # 路由层：只收请求、调服务、返回响应
│   ├── users.py
│   ├── teams.py
│   ├── knowledge_bases.py
│   ├── conversations.py
│   ├── messages.py
│   ├── chat.py
│   ├── code_assist.py
│   ├── doc_generator.py
│   └── health.py
├── services/                # 服务层：业务逻辑 + AI 编排
│   ├── user_service.py
│   ├── knowledge_service.py
│   ├── chat_service.py
│   ├── code_assist_service.py
│   ├── doc_generator_service.py
│   └── ai/                  # AI 只出现在这里
│       ├── llm_client.py    # 百炼大模型封装
│       ├── conversation_summary.py  # 对话历史摘要工具
│       ├── rag_pipeline.py  # RAG 检索链路
│       └── agent_graph.py   # LangGraph 状态机
├── repositories/            # 数据访问层：CRUD / 向量 / 缓存
├── models/                  # SQLAlchemy 表模型
└── schemas/                 # Pydantic 请求/响应模型
```

**分层约束（记住这三条就够）：**

| 层级 | 可以做什么 | 不可以做什么 |
|------|------------|--------------|
| 路由层 | 校验参数、调服务、返回 JSON | 直接操作数据库、直接调 AI |
| 服务层 | 业务逻辑、事务、调 AI 与 Repository | 直接写 SQL、构造 HTTP 响应 |
| 数据访问层 | MySQL / Milvus / Redis 读写 | 写业务判断 |

---

## 四、已挂载的 API 前缀

| 模块 | 前缀 | 说明 |
|------|------|------|
| 健康检查 | `/health` | 服务是否活着 |
| 认证 | `/api/v1/auth` | 注册、登录等 |
| 用户 | `/api/v1/users` | 用户资料等 |
| 团队 | `/api/v1/teams` | 团队管理 |
| 超级管理员 | `/api/v1/admin` | 组织树、用户启停 |
| 知识库 | `/api/v1/knowledge-bases` | 知识库列表等 |
| 对话 | `/api/v1/conversations` | 消息列表等 |
| 消息 | `/api/v1/messages` | 历史消息、删除消息 |
| 发起对话 | `/api/v1/message` | `POST /chat` 发送消息并获取回复 |
| 智能问答 | `/api/v1/chat` | `POST /ask` 发起问答 |
| 代码辅助 | `/api/v1/code-assist` | `POST /assist` |
| 文档生成 | `/api/v1/doc-generator` | `POST /generate` |

每个业务模块都提供了 `GET .../status`，用来确认路由已就绪。

需要登录的接口，请求头加上：

```text
Authorization: Bearer <access_token>
```

鉴权中间件会校验 Token 签名、有效期、黑名单及 Redis 登录态，并将 `user_id`、`team_id` 注入 `request.state`；**角色不入 Token**，需通过 `team_members` 表按 `user_id + team_id` 实时查询。同时滑动刷新 `session:login:{user_id}` 的 TTL（默认 30 分钟）。

路由层通过 `dependencies.py` 中的依赖做角色校验：

| 依赖 | 含义 |
|------|------|
| `CurrentUser` | 已登录，且为 Token 当前团队成员 |
| `TeamMemberUser` | 已登录，且为路径 `team_id` 的团队成员 |
| `TeamAdminUser` | 已登录，且为路径 `team_id` 的 **admin** |
| `SuperAdminUser` | 已登录，且 `user_id` 为配置的超级管理员（默认 `15`） |

角色不在允许范围内时返回 `403`，message 为「暂无对应角色权限」或「仅超级管理员可操作」。

以下路径无需 Token：`/health`、`/docs`、`/api/v1/auth/register|login|refresh`、各模块 `/status`。

统一响应格式：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 用户注册 `POST /api/v1/auth/register`

请求体：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "your-password"
}
```

- `username`：3–50 字符
- `email`：合法邮箱格式
- `password`：非空（强度校验由前端负责）

成功响应 `201`，`data` 示例：

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "team_id": 1,
    "role": "admin",
    "is_active": true
  }
}
```

- Access Token 有效期 2 小时，Refresh Token 7 天
- 用户名或邮箱已存在时返回 `409 Conflict`

### 用户登录 `POST /api/v1/auth/login`

请求体：

```json
{
  "number": "alice",
  "password": "your-password"
}
```

- `number`：用户名或邮箱
- `password`：非空

成功响应 `200`，`data` 结构与注册接口相同。

- 用户不存在时返回 `404`，message 为「用户不存在」
- 密码错误时返回 `401`，message 为「密码错误」

### 获取当前用户 `GET /api/v1/auth/me`

无请求参数，请求头需携带 `Authorization: Bearer <access_token>`。

成功响应 `data` 示例：

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "role": "admin",
  "team_id": 1,
  "is_super_admin": false
}
```

### Token 续期 `POST /api/v1/auth/refresh`

请求体：

```json
{
  "refresh_token": "<jwt>"
}
```

成功响应 `200`，`data` 结构与登录接口相同（新的双 Token + 用户基本信息）。

- Refresh Token 无效或已过期时返回 `401`
- jti 已在黑名单 `session:blacklist:{jti}` 中时返回 `401`
- 续期成功后，旧 Refresh Token 的 jti 会写入黑名单，TTL 为其剩余有效期

### 用户登出 `POST /api/v1/auth/logout`

请求头需携带 `Authorization: Bearer <access_token>`。

成功响应：

```json
{
  "code": 0,
  "message": "登出成功",
  "data": null
}
```

- 将当前 Access Token 的 `jti` 写入黑名单，TTL 为剩余有效期
- 删除 Redis `session:login:{user_id}`

### 切换团队 `POST /api/v1/auth/switch-team`

请求头需携带 `Authorization: Bearer <access_token>`。

请求体：

```json
{
  "team_id": 2
}
```

成功响应 `200`，`data` 结构与登录接口相同（新的双 Token + 用户基本信息，含新 `team_id` 与 `role`）。

- 用户未加入目标团队时返回 `403`
- 切换成功后旧 Access Token 的 `jti` 会写入黑名单
- Token 续期（`refresh`）会优先使用 Redis 会话中的 `team_id`，与当前团队保持一致

### 我的团队列表 `GET /api/v1/teams/mine`

请求头需携带 `Authorization: Bearer <access_token>`，用于切换团队前展示可选团队。

成功响应 `data` 示例：

```json
[
  {
    "id": 1,
    "name": "研发团队",
    "role": "admin",
    "is_current": true
  },
  {
    "id": 2,
    "name": "产品团队",
    "role": "developer",
    "is_current": false
  }
]
```

- `is_current` 表示是否为 Token 中的当前团队
- 不含已解散的团队

### 生成邀请码 `POST /api/v1/teams/{team_id}/invites`

请求头需携带 `Authorization: Bearer <access_token>`，仅团队 **admin** 可操作。

成功响应 `201`，`data` 示例：

```json
{
  "invite_code": "xYz9AbC...",
  "expires_at": "2026-08-07T03:23:00Z",
  "team_id": 1
}
```

- 邀请码有效期 **7 天**，存储于 Redis `invite:code:{code}`
- **一次性**：有人使用邀请码成功申请入团后，该码立即失效

### 申请加入团队 `POST /api/v1/teams/join`

请求头需携带 `Authorization: Bearer <access_token>`。

请求体：

```json
{
  "invite_code": "xYz9AbC..."
}
```

成功响应 `201`，`data` 示例：

```json
{
  "request_id": "uuid",
  "team_id": 1,
  "team_name": "研发团队",
  "status": "pending"
}
```

- 邀请码无效或已过期时返回 `404`
- 已是团队成员或已有待审批申请时返回 `409`
- 审批记录仅存 Redis，不落库：`join_request:{request_id}` + `team:join_pending:{team_id}`

### 查看入团审批 `GET /api/v1/teams/{team_id}/join-requests`

仅团队 **admin** 可操作。成功响应 `data` 为审批列表：

```json
[
  {
    "request_id": "uuid",
    "user_id": 2,
    "username": "bob",
    "created_at": "2026-07-31T03:23:00Z",
    "status": "pending"
  }
]
```

### 审批通过 `POST /api/v1/teams/{team_id}/join-requests/{request_id}/approve`

仅团队 **admin** 可操作。请求体：

```json
{
  "role": "developer"
}
```

- `role` 可选：`admin`、`tech_lead`、`developer`
- 审批通过后写入 `team_members` 表，并清理 Redis 审批记录

### 拒绝入团申请 `POST /api/v1/teams/{team_id}/join-requests/{request_id}/reject`

仅团队 **admin** 可操作，仅清理 Redis 审批记录，不写库。

### 分配成员角色 `PUT /api/v1/teams/{team_id}/members/{user_id}/role`

仅团队 **admin** 可操作。请求体：

```json
{
  "role": "developer"
}
```

- `role` 可选：`admin`、`tech_lead`、`developer`
- 团队**必须有且只有一个 admin**
- admin 可将 admin 权限**转让**给其他成员：将目标成员设为 `admin` 后，原 admin 自动降为 `developer`
- 不可直接将 admin 降为其他角色，需先转让
- 成功响应 `200`，`message` 为「角色已更新」

### 移除团队成员 `DELETE /api/v1/teams/{team_id}/members/{user_id}`

仅团队 **admin** 可操作。

- 不可直接移除当前管理员，需先转让 admin 权限
- 成功响应 `200`，`message` 为「成员已移除」

### 解散团队 `DELETE /api/v1/teams/{team_id}`

仅团队 **admin** 可操作。

- 若团队仍有关联知识库，返回 `409 Conflict`，提示「请先清理团队关联的知识库数据」
- 成功响应 `200`，`message` 为「团队已解散」

### 超级管理员

超级管理员由配置项 `SUPER_ADMIN_USER_ID` 指定（默认 `15`），**不修改 users 表结构**。可在 `.env` 中覆盖：

```env
SUPER_ADMIN_USER_ID=15
```

#### 获取组织树 `GET /api/v1/admin/organization`

仅 **超级管理员** 可操作。返回按团队分组的树形结构，每个团队下的成员按 **admin → tech_lead → developer** 排序。

成功响应 `data` 示例：

```json
{
  "teams": [
    {
      "id": 1,
      "name": "研发团队",
      "description": null,
      "member_count": 3,
      "members": [
        {
          "id": 1,
          "username": "alice",
          "email": "alice@example.com",
          "role": "admin",
          "is_active": true,
          "is_super_admin": true
        },
        {
          "id": 2,
          "username": "bob",
          "email": "bob@example.com",
          "role": "tech_lead",
          "is_active": true,
          "is_super_admin": false
        }
      ]
    }
  ],
  "unassigned_users": []
}
```

- `unassigned_users`：未加入任何团队的用户（`role` 为空字符串）
- 同一用户加入多个团队时，会在各团队的 `members` 中分别出现

#### 启用/停用用户 `PUT /api/v1/admin/users/{user_id}/status`

仅 **超级管理员** 可操作。请求体：

```json
{
  "is_active": false
}
```

- `true` 启用用户，`false` 停用用户
- 停用后该用户 Redis 登录会话立即清除，无法再使用已有 Token
- 超级管理员不能停用自己的账号
- 成功响应 `200`，`message` 为「用户已启用」或「用户已停用」

### 历史消息 `POST /api/v1/messages/getMessageList`

请求头需携带 `Authorization: Bearer <access_token>`。

请求体：

```json
{
  "conversationId": 1,
  "page": 1,
  "pageSize": 20
}
```

- `conversationId`：对话 ID
- `page`：页码，从 1 开始
- `pageSize`：每页条数，1–100

成功响应 `data` 示例：

```json
{
  "items": [
    {
      "id": 1,
      "role": "user",
      "content": "你好",
      "created_at": "2026-08-03T10:00:00"
    }
  ],
  "total": 1,
  "page": 1
}
```

- 消息按创建时间正序排列
- 对话不存在时返回 `404`，message 为「对话不存在」
- 消息列表会缓存到 Redis，Key 为 `conv:msg:{conversation_id}`，TTL 15 分钟；命中缓存时滑动续期，未命中时查库并回填

### 删除消息 `POST /api/v1/messages/remove`

请求头需携带 `Authorization: Bearer <access_token>`。

请求体：

```json
{
  "messageId": 1,
  "conversationId": 1
}
```

- 成功响应 `200`，`message` 为「消息已删除」
- 消息不存在或不属于当前用户对话时返回 `404`，message 为「消息不存在」

### 发起对话 `POST /api/v1/messages/chat`

请求头需携带 `Authorization: Bearer <access_token>`。

响应类型为 **SSE 流式**（`Content-Type: text/event-stream`），前端请使用 `EventSource` 或 `fetch` + `ReadableStream` 消费。

请求体：

```json
{
  "content": "帮我写一个 FastAPI 登录接口",
  "content_type": "text",
  "conversation_id": 1
}
```

- `content`：用户消息内容（必填）
- `content_type`：`text` 或 `code`
- `conversation_id`：对话 ID；**首次发起可不传**，系统会自动创建会话，标题取用户消息前 20 字

SSE 事件说明：

| event | data 说明 |
|-------|-----------|
| `conversation` | 新建会话时返回 `{"conversation_id": 1}` |
| `user_msg` | 用户消息对象（含 id、role、content 等） |
| `delta` | 助手回复增量 `{"content": "..."}` |
| `assistant_msg` | 助手完整消息对象（落库后） |
| `done` | 流结束，`data` 为 `null` |
| `error` | 错误信息 `{"code": 40900, "message": "..."}` |

示例流：

```
event: user_msg
data: {"id": 1, "role": "user", "content": "...", "content_type": "text", "created_at": "..."}

event: delta
data: {"content": "可以"}

event: delta
data: {"content": "使用 JWT"}

event: assistant_msg
data: {"id": 2, "role": "assistant", "content": "可以使用 JWT...", ...}

event: done
data: null
```

处理流程：

1. 获取分布式锁 `conv:lock:{conversation_id}`（SETNX，TTL 30s），失败返回 `409`，message 为「消息处理中」
2. 保存用户消息到数据库（`role=user`）
3. 将用户消息追加到 Redis `conv:msg:{conversation_id}`，刷新 TTL 15 分钟
4. 获取上下文；超过 20 条时调用 LLM 摘要，写入 system 提示词，并保留最近 10 条完整消息
5. 保存助手回复到数据库与 Redis
6. 更新会话 `updated_at`，用于列表排序
7. 释放分布式锁

---

位于 `app/services/ai/conversation_summary.py`，供后续 chat / Agent 使用：当历史记录过长，可将较早的消息压缩为摘要并放入系统提示词。

**LangChain Tool（供 Agent 导入）：**

```python
from app.services.ai.conversation_summary import (
    DEFAULT_AGENT_TOOLS,
    summarize_conversation_history_tool,
)

# 创建 Agent 时传入
agent = create_agent(llm, tools=DEFAULT_AGENT_TOOLS)
# 或单独使用
tools = [summarize_conversation_history_tool]
```

**业务层直接调用：**

```python
from app.services.ai.conversation_summary import summarize_messages

messages = [
    {"role": "user", "content": "帮我写一个 FastAPI 登录接口"},
    {"role": "assistant", "content": "可以使用 JWT 做鉴权..."},
]
summary = await summarize_messages(messages)
```

- Tool 入参 `messages_json`：JSON 字符串格式的历史消息列表
- 输出：不超过 200 字的中文摘要字符串
- API Key 从 `.env` 的 `DASHSCOPE_API_KEY` 读取
- 未配置 Key 或 LLM 调用失败时，自动降级为截断版摘要
- **当前不做 Redis 缓存**

---

## 五、常用命令

| 做什么 | 命令 |
|--------|------|
| 安装依赖 | `pip install -r requirements.txt` |
| 启动（热重载） | `uvicorn app.main:app --reload --port 8000` |
| 查看接口文档 | 浏览器打开 `/docs` |

---

## 六、当前进度与后续改进

### 已完成

- [x] 按选型文档搭好 FastAPI + 三层目录骨架  
- [x] 统一 `/api/v1` 前缀与各模块路由占位  
- [x] 异步 SQLAlchemy 引擎/会话依赖  
- [x] AI 调用边界（仅 `services/ai/`）  
- [x] README、`.env.example`、`.gitignore`  
- [x] 关联 GitHub 公开仓库  
- [x] 切换团队 `POST /api/v1/auth/switch-team`（重签 Token）  
- [x] 邀请入团流程（邀请码生成、申请、Redis 审批通过/拒绝）  
- [x] 超级管理员组织树与用户启停（`/api/v1/admin`）  
- [x] 消息历史分页与删除（`/api/v1/messages`）  
- [x] 发起对话（`POST /api/v1/message/chat`）  
- [x] 对话历史摘要 LangChain Tool（`summarize_conversation_history_tool`）  

### 建议下一步

1. 配好本机 MySQL，用 Alembic 做正式建表迁移  
2. 把演示鉴权换成真实 JWT / Session  
3. 接入百炼 `DASHSCOPE_API_KEY`，打通真正的问答链路  
4. 接入 Milvus 与 Redis 的真实读写  
5. 与前端 `dev-smart-assistant-frontend` 联调登录与流式对话  

### 已知注意点

- 骨架阶段 Repository / AI 多为占位实现，不会真正连库或调模型  
- 启动健康检查与各模块 `/status` **不依赖** MySQL；带 `DbSession` 的接口在真正执行 SQL 前一般也不会立刻连库，但正式业务开发前请先配好 `.env` 中的 `DATABASE_URL`  
- Python 本机若是 3.13，满足「3.12+」要求；团队若统一 3.12，可在虚拟环境中指定 3.12 解释器  

---

## 七、和前端的关系

| 项目 | 路径 |
|------|------|
| 前端 | `D:\agentProject\dev-smart-assistant-frontend` |
| 后端（本仓库） | `D:\agentProject\dev-smart-assistant-backend` |

前端默认请求后端 API；后端 CORS 已在开发环境放开，本地联调可直接调用。
