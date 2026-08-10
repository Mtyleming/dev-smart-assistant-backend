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
│   ├── document_parser/     # 文档解析策略（pdf/docx/txt/md）
│   ├── document_chunker.py  # 文档切片（RecursiveCharacterTextSplitter）
│   ├── document_index_service.py  # 切块→向量化→Milvus 编排
│   ├── reranker_service.py  # 百炼 gte-rerank 文本重排
│   ├── chat_service.py
│   ├── code_assist_service.py
│   ├── doc_generator_service.py
│   ├── route/               # 意图路由策略（策略模式）
│   │   ├── base.py          # 策略接口
│   │   ├── factory.py       # 按 intent 选择策略
│   │   ├── knowledge_query_route.py  # 知识库查询 → rag（已接 RAG）
│   │   ├── general_qa_route.py       # 通用问答 → general
│   │   ├── code_request_route.py     # 代码辅助 → code
│   │   └── doc_generation_route.py   # 文档生成 → doc
│   └── ai/                  # AI 只出现在这里
│       ├── llm_client.py    # 百炼大模型对话 / RAG 生成
│       ├── embedding_service.py  # 文本向量化工具（上传与查询共用）
│       ├── conversation_summary.py  # 对话历史摘要工具
│       ├── intent_service.py        # 意图识别（四类意图）
│       ├── intent_router.py         # LangGraph 四节点分发
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
| `CurrentTeamAdminOrLead` | 已登录，且当前团队角色为 **admin** 或 **tech_lead** |
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

### 知识库

知识库归属 **Token 当前团队**；创建/修改/删除仅 **admin**、**tech_lead** 可操作，列表与详情对全体成员开放。

删除时先按 `knowledge_base_id + team_id` 清理 Milvus 向量与 MySQL `document_chunks`，成功后再删 MySQL 知识库；向量清理失败则整次失败，库记录保留。

**上传文档前请先启动 Milvus**（否则切片/向量化成功后会在写入阶段返回 503）。

本地常用两种方式（二选一）：

1. **milvus-server**（你当前用法）  
   ```bash
   milvus-server --data D:\milvus_data
   ```
2. **Docker**  
   ```bash
   docker compose -f docker-compose.milvus.yml up -d
   ```

确认 `.env` 中 `MILVUS_URI=http://127.0.0.1:19530` 后，再上传/删除文档。  
说明：本地 `milvus-server` 删除时只支持主键，代码已改为「先按条件查出 id，再按 id 删除」。

相关环境变量（见 `.env.example`）：

```env
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=document_chunks
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=10
```

#### 创建知识库 `POST /api/v1/knowledge-bases/create`

请求体：

```json
{
  "name": "产品需求库",
  "description": "存放 PRD 与需求说明"
}
```

成功响应 `201`，`data` 示例：`{"id": 1}`，`message` 为「创建成功」。

- 同团队名称重复时返回 `409`，message 为「知识库名称已存在」
- 开发者调用返回 `403`

#### 分页列表 `POST /api/v1/knowledge-bases/page`

请求体：

```json
{
  "page": 1,
  "pageSize": 20,
  "keyword": "需求"
}
```

- `page`：页码，从 1 开始
- `pageSize`：每页条数，1–100
- `keyword`：可选，按名称模糊搜索

成功响应 `data` 示例：

```json
{
  "items": [
    {
      "id": 1,
      "name": "产品需求库",
      "description": "存放 PRD 与需求说明",
      "team_id": 1,
      "created_by": 2,
      "created_at": "2026-08-04T10:00:00",
      "updated_at": "2026-08-04T10:00:00"
    }
  ],
  "total": 1,
  "page": 1
}
```

#### 详情 `POST /api/v1/knowledge-bases/getById`

请求体：`{"id": 1}`

- 不存在或不属于当前团队时返回 `404`，message 为「知识库不存在」

#### 修改 `POST /api/v1/knowledge-bases/update`

请求体：

```json
{
  "id": 1,
  "name": "新名称",
  "description": "新描述"
}
```

- `name`、`description` 均为可选，但至少提供一个；未传字段保持原值
- `description` 传 `null` 可清空描述
- 成功响应 `message` 为「更新成功」

#### 删除 `POST /api/v1/knowledge-bases/delete`

请求体：`{"id": 1}`

- 成功响应 `message` 为「删除成功」
- Milvus 清理失败时返回 `503`，message 为「向量数据清理失败，知识库未删除」

#### 上传文档 `POST /api/v1/knowledge-bases/createDocuments`

请求类型：`multipart/form-data`，权限：**admin**、**tech_lead**。

表单字段：

| 字段 | 说明 |
|------|------|
| `kb_id` | 知识库 ID |
| `file` | 文档文件（`pdf` / `docx` / `md` / `txt`），**单文件 ≤ 20MB** |

处理流程：

1. 校验知识库属于当前团队  
2. 在 `documents` 表新增记录，`status=uploading`  
3. 文件保存到本地 `uploads/{team_id}/{kb_id}/`，随后 `status=parsing`  
4. **按文件类型走策略模式解析**（PDF / Word / TXT / Markdown 各自独立策略）  
5. 解析全文写入 `documents.full_text`，成功则 `status=completed`；失败则 `status=failed`  
6. **切片 → 写入 MySQL `document_chunks` → Embedding → 写入 Milvus**（内部解耦，不新增对外接口）  
   - 切片：`RecursiveCharacterTextSplitter`，512 tokens / 重叠 64 tokens  
   - MySQL：存 `chunk_id`、`document_id`、`chunk_index`、`content`、`knowledge_base_id`、`team_id`  
   - 向量化：`embedding_service`（百炼 `text-embedding-v4`，默认 1024 维，每批最多 10 条；与 RAG 查询共用）  
   - Milvus：另存向量及同样的切块元数据字段  
   - 切片/向量化/写入失败时文档改为 `failed`，并返回错误  

> Swagger `/docs` 说明：若 `file` 变成普通文本框无法选文件，请重启服务后强刷页面（Ctrl+F5）。项目已在 OpenAPI 中补回 `format: binary`，以兼容 Swagger UI。

成功响应 `201`，`data` 示例：`{"id": 1}`，`message` 为「上传成功」。

解析失败时返回 `400`，`message` 为具体原因（如加密 PDF、损坏的 Word 等）。  
向量化或写入 Milvus 失败时返回 `503`。

相关环境变量：

```env
UPLOAD_DIR=uploads
UPLOAD_MAX_BYTES=20971520
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=document_chunks
```

若数据库已有 `documents` 表但没有 `full_text` 列，请执行：

```bash
# MySQL 中执行
source scripts/add_documents_full_text.sql
```

或手动：

```sql
ALTER TABLE documents
  ADD COLUMN full_text LONGTEXT NULL COMMENT '文档解析全文' AFTER file_size;
```

若还没有 `document_chunks` 表，请执行：

```bash
source scripts/create_document_chunks.sql
```

若表已存在但是旧结构（缺少 `chunk_id` / `knowledge_base_id` / `team_id`），请执行：

```bash
.\.venv\Scripts\python.exe scripts\migrate_document_chunks.py
```

或手动执行 [`scripts/alter_document_chunks_add_fields.sql`](scripts/alter_document_chunks_add_fields.sql)。
解析策略目录：`app/services/document_parser/`（工厂按 `file_type` 选择策略）。  
切片：`app/services/document_chunker.py`；索引编排：`app/services/document_index_service.py`。

#### 文档详情 `POST /api/v1/knowledge-bases/getDocumentById`

权限：当前团队任意成员。请求体：`{"document_id": 1}`

- 不存在、已软删或不属于当前团队时返回 `404`，message 为「文档不存在」

成功 `data` 示例：

```json
{
  "id": 1,
  "knowledge_base_id": 1,
  "title": "需求说明.pdf",
  "file_type": "pdf",
  "file_path": "uploads/1/1/xxx_需求说明.pdf",
  "file_size": 1024,
  "status": "completed",
  "full_text": "……解析后的全文……",
  "created_at": "2026-08-05T10:00:00",
  "updated_at": "2026-08-05T10:00:00"
}
```

- 详情接口返回 `full_text`；分页列表不返回全文（`full_text` 为 `null`），避免大字段拖慢列表

#### 文档分页列表 `POST /api/v1/knowledge-bases/pageDocuments`

权限：当前团队任意成员。请求体：

```json
{
  "kb_id": 1,
  "page": 1,
  "pageSize": 20,
  "keyword": "需求"
}
```

- 仅返回该知识库下、且未软删（`status != deleted`）的文档
- `keyword` 可选，按标题模糊搜索
- 排序：`updated_at` 降序

#### 删除文档 `POST /api/v1/knowledge-bases/deleteDocumentById`

权限：**admin**、**tech_lead**。请求体：`{"document_id": 1}`

- 先按 `document_id + team_id` 清理 Milvus 向量与 MySQL `document_chunks`，成功后再软删除（`status` 改为 `deleted`）；本地文件本次保留  
- 向量清理失败时返回 `503`，message 为「向量数据清理失败，文档未删除」，MySQL 记录不变  
- 成功响应 `message` 为「删除成功」

### 发起对话 `POST /api/v1/messages/chat`

请求头需携带 `Authorization: Bearer <access_token>`。

响应类型为 **SSE 流式**（`Content-Type: text/event-stream`），前端请使用 `EventSource` 或 `fetch` + `ReadableStream` 消费。

请求体：

```json
{
  "content": "项目里登录接口怎么写？",
  "content_type": "text",
  "conversation_id": 1,
  "knowledge_base_id": 3
}
```

- `content`：用户消息内容（必填）
- `content_type`：`text` 或 `code`
- `conversation_id`：对话 ID；**首次发起可不传**，系统会自动创建会话，标题取用户消息前 20 字
- `knowledge_base_id`：可选；指定则只查该知识库，不传则查当前团队下全部知识库

SSE 事件说明：

| event | data 说明 |
|-------|-----------|
| `conversation` | 新建会话时返回 `{"conversation_id": 1}` |
| `user_msg` | 用户消息对象（含 id、role、content 等） |
| `delta` | 助手回复增量 `{"content": "..."}` |
| `citation_verified` | （仅 RAG）流结束后若引用编号被清洗，返回校正后的全文与 sources |
| `assistant_msg` | 助手完整消息对象（含 `content`、`sources`） |
| `done` | 流结束，`data` 为 `{"sources": [...]}`；每项含 `ref`、`document_id`、`chunk_index`、`content`（切片正文）等 |
| `error` | 错误信息 `{"code": 40900, "message": "..."}` |

处理流程：

1. 获取分布式锁；保存用户消息到 MySQL / Redis  
2. **意图识别**：`knowledge_query` 走 RAG，其它意图走通用对话  
3. RAG 路径：检索 Top5 → 重排 Top3 → 组装提示词（系统提示 + `[1][2][3]` 上下文 + 最近 3 轮历史 + 当前问题）→ 流式生成  
4. 流结束后校验回答中的 `[n]` 是否对应真实切块；无效编号删除；`sources` 只保留真实引用，并带上切片正文 `content`  
5. 助手完整 `content` 与 `sources` 写入 `messages` 表并回写 Redis；`done` 事件同步返回 `sources`  
6. 释放分布式锁  

若数据库已有 `messages` 表但没有 `sources` 列，请执行：

```bash
# MySQL
source scripts/add_messages_sources.sql
# 或
$env:PYTHONPATH="."
python scripts/migrate_messages_sources.py
```

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
- [x] 知识库 CRUD（`/api/v1/knowledge-bases`：创建/分页/详情/修改/删除，删除前清 Milvus）  
- [x] 知识库文档接口（上传/详情/分页/软删除；策略模式解析全文入库）  
- [x] 知识库文档切块与 Embedding 入库（Milvus；切片与向量化解耦）  
- [x] Embedding 工具类抽离（`embedding_service`，上传与 RAG 查询共用 `text-embedding-v4`）  
- [x] RAG 检索链路（向量 Top5 → gte-rerank Top3 → 置信度 → 上下文组装 → 生成）  
- [x] 意图识别（`intent_service`）+ LangGraph 四节点路由（`intent_router`）  
- [x] 意图路由策略（`knowledge_query` 已接 RAG；其余三类仍为占位）  

### 意图识别与路由（当前）

用户当前消息经 `classify_intent`（**只看当前输入，不看历史**）分为四类，再由 LangGraph 分发到对应节点；节点内用策略模式执行：

| 意图 | LangGraph 节点 | 策略类 | 说明 |
|------|----------------|--------|------|
| `knowledge_query` | `rag` | `KnowledgeQueryRouteStrategy` | 已接入 RAG 知识库查询 |
| `general_qa` | `general` | `GeneralQaRouteStrategy` | 通用技术问答（占位） |
| `code_request` | `code` | `CodeRequestRouteStrategy` | 代码解读/生成/审查（占位） |
| `doc_generation` | `doc` | `DocGenerationRouteStrategy` | 生成技术文档（占位） |

- API Key：使用 `.env` 的 `DASHSCOPE_API_KEY`（对应 `settings.llm_api_key`）  
- 意图置信度 `< 0.7` 或解析失败时，回退为 `general_qa`  
- 识别结果缓存 Redis：`intent:{conversation_id}:{msg_hash}`，TTL 300 秒  
- `IntentState` 可传 `team_id`、`kb_ids`（空列表 = 查团队下全部知识库）  
- **chat 已接入**：`POST /api/v1/messages/chat` 会先意图识别；`knowledge_query` 走 RAG（含引用校验与 `sources` 落库），其它意图走通用对话  

### RAG 知识库查询流程

1. 用户问题经 `embedding_service`（`text-embedding-v4`，1024 维）向量化  
2. Milvus 按 `team_id`（及可选 `kb_ids`）过滤，取向量相似 Top5  
3. 百炼 `gte-rerank` 重排后取 Top3  
4. 置信度（看 Top-1 的 Reranker 分数 + 多块一致性）：  
   - **高**（≥ 0.8，且 Top-2/Top-3 均 ≥ 0.5）：正常 RAG 回答  
   - **中**（0.5～0.8，或高分但不一致）：回答并提示「建议进一步确认」  
   - **低**（&lt; 0.5 或无结果）：放弃检索，降级通用问答，并告知「知识库中未找到相关信息」  
5. 提示词结构：系统提示（RAG）+ 编号上下文 `[1][2][3]`（含切块内容与来源文档 ID）+ 最近 3 轮对话历史 + 当前用户问题  
6. 流式结束后校验引用编号；助手 `content` 与真实 `sources` 写入 `messages` 表  

相关环境变量：

```env
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
RERANK_MODEL=gte-rerank-v2
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=document_chunks
```

> 若日志出现重排 `403 Access denied`：到[百炼模型广场](https://bailian.console.aliyun.com/)开通 `gte-rerank-v2`（或把 `.env` 的 `RERANK_MODEL` 改成已开通的文本排序模型）。未开通时系统会自动按向量检索顺序降级，对话仍可用。

用法示例：

```python
from app.services.ai.intent_service import classify_intent
from app.services.ai.intent_router import intent_graph
from app.services.route import get_route_strategy

# 1) 识别意图
result = await classify_intent(message, conversation_id, redis)
# {"intent": "knowledge_query", "confidence": 0.92}

# 2) LangGraph 分发（知识库查询需传 team_id；kb_ids 可选）
final = await intent_graph.ainvoke({
    "message": message,
    "conversation_id": conversation_id,
    "intent": result["intent"],
    "confidence": result["confidence"],
    "result": {},
    "team_id": team_id,
    "kb_ids": [],  # 空 = 当前团队全部知识库
})

# 3) 也可直接按意图取策略
strategy = get_route_strategy(result["intent"])
data = await strategy.run(
    message,
    conversation_id,
    team_id=team_id,
    kb_ids=[],
)
```

**本地怎么测意图识别（推荐）**

1. 确认 `.env` 里已填写 `DASHSCOPE_API_KEY`  
2. 在项目根目录执行：

```bash
.\.venv\Scripts\Activate.ps1
python test/test_intent_classify.py
```

脚本会自动跑 8 句样例（四类意图各 2 句），打印识别出的意图、置信度、对应节点；Redis 没开也能测（会自动改用内存缓存）。

想自己输入一句话再测：

```bash
python test/test_intent_classify.py --ask
```

### 建议下一步

1. 配好本机 MySQL，用 Alembic 做正式建表迁移  
2. 补全 `general` / `code` / `doc` 三个策略的真实 run 逻辑  
3. 与前端联调：消费 `sources`、`citation_verified` 事件展示引用  

### 已知注意点

- `knowledge_query` 已接 RAG，且 **chat 接口已按意图分流**；`general` / `code` / `doc` 策略仍为占位  
- 文档上传已完成切块与 Embedding 入库；知识库/文档删除会清理对应 Milvus 向量（Collection 不存在时跳过清理）  
- 若 chat 报未知列 `sources`，请先执行 `scripts/add_messages_sources.sql` 或 `scripts/migrate_messages_sources.py`  
- 扫描版 PDF（纯图片）可能解析出空文本，需后续 OCR 增强；空文本会跳过向量写入  
- **文档上传返回 503「文档向量化失败」**：多半不是 Milvus 坏了，而是调用百炼 Embedding 时走了本机代理（如 `127.0.0.1:7897`）却连不上。`embedding_service` 已对百炼请求设置 `trust_env=False`（直连、忽略系统代理）。若仍失败：① 确认能访问 `dashscope.aliyuncs.com`；② 检查 `.env` 的 `DASHSCOPE_API_KEY`；③ 失败文档需重新上传（当前无单独「重新向量化」接口）  
- 启动健康检查与各模块 `/status` **不依赖** MySQL；带 `DbSession` 的接口在真正执行 SQL 前一般也不会立刻连库，但正式业务开发前请先配好 `.env` 中的 `DATABASE_URL`  
- Python 本机若是 3.13，满足「3.12+」要求；团队若统一 3.12，可在虚拟环境中指定 3.12 解释器  
- 若启动报 `ModuleNotFoundError`，请在已激活的 `.venv` 中执行 `pip install -r requirements.txt`。对话相关还依赖 `langchain-core`、`langchain-qwq`、`langgraph`、`openai`、`dashscope`；文档切片依赖 `langchain-text-splitters`、`tiktoken`；文档解析依赖 `pypdf`、`python-docx`  
- **Cursor 全局 MySQL MCP**：已在 `%USERPROFILE%\.cursor\mcp.json` 配置 `@kyruntime/mysql-mcp`，连接本机 `127.0.0.1:3306`（默认库 `dev_assistant`）。修改账号后需在 Cursor 的 **Settings → MCP** 里刷新/重启该服务；写操作默认关闭（只读查询更安全）

---

## 七、和前端的关系

| 项目 | 路径 |
|------|------|
| 前端 | `D:\agentProject\dev-smart-assistant-frontend` |
| 后端（本仓库） | `D:\agentProject\dev-smart-assistant-backend` |

前端默认请求后端 API；后端 CORS 已在开发环境放开，本地联调可直接调用。
