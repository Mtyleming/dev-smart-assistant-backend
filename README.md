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
| 知识库 | `/api/v1/knowledge-bases` | 知识库列表等 |
| 对话 | `/api/v1/conversations` | 消息列表等 |
| 智能问答 | `/api/v1/chat` | `POST /ask` 发起问答 |
| 代码辅助 | `/api/v1/code-assist` | `POST /assist` |
| 文档生成 | `/api/v1/doc-generator` | `POST /generate` |

每个业务模块都提供了 `GET .../status`，用来确认路由已就绪。

需要登录的接口，请求头加上：

```text
Authorization: Bearer <access_token>
```

鉴权中间件会校验 Token 签名、有效期、黑名单及 Redis 登录态，并将 `user_id`、`team_id`、`role` 注入 `request.state`；同时滑动刷新 `session:login:{user_id}` 的 TTL（默认 30 分钟）。

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
  "team_id": 1
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
