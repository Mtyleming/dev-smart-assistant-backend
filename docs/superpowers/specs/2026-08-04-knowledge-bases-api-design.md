# 知识库管理接口设计

日期：2026-08-04  
状态：已确认，实现中

## 1. 背景与目标

为「开发智能助手」后端补齐知识库 CRUD 能力，对接已有表 `knowledge_bases`，并在删除时先清理 Milvus 向量再删除 MySQL 记录。

团队隔离以登录 Token 中的当前 `team_id` 为准，前端无需传 `teamId`。

## 2. 已确认需求

| 项 | 结论 |
|----|------|
| 团队范围 | Token 当前团队（方案 A） |
| 分页 | `page` + `pageSize`，可选 `keyword` 按名称模糊搜索 |
| 创建成功返回 | 仅返回 `{"id": <新知识库ID>}` |
| 修改字段 | `id` + 可选 `name`/`description`，至少改一项 |
| 删除策略 | 先清 Milvus（按 `knowledge_base_id` + `team_id`），成功后再删 MySQL；Milvus 失败则整次失败 |
| 实现方式 | 沿用路由 → 服务 → Repository 三层（方案 1） |

角色约定（与 `team_members.role` 一致）：

- 创建 / 修改 / 删除：`admin`、`tech_lead`
- 分页列表 / 按 ID 详情：当前团队任意成员（`admin` / `tech_lead` / `developer`）

## 3. 接口设计

前缀：`/api/v1/knowledge-bases`  
统一响应：`{ "code": 0, "message": "ok", "data": ... }`  
鉴权：请求头 `Authorization: Bearer <access_token>`

### 3.1 创建知识库 `POST /create`

权限：`admin`、`tech_lead`

请求体：

```json
{
  "name": "产品需求库",
  "description": "存放 PRD 与需求说明"
}
```

- `name`：必填，1–200 字符
- `description`：可选

成功：`data` 为 `{"id": 1}`，`message` 可为「创建成功」

错误：

- 同团队已存在同名知识库 → `409`，message「知识库名称已存在」
- 无权限 → `403`，「暂无对应角色权限」

写入字段：`name`、`description`、`team_id`（Token）、`created_by`（当前用户 ID）

### 3.2 分页列表 `POST /page`

权限：当前团队任意成员

请求体：

```json
{
  "page": 1,
  "pageSize": 20,
  "keyword": "需求"
}
```

- `page`：默认 1，≥1
- `pageSize`：默认 20，1–100
- `keyword`：可选；有值时对 `name` 做模糊匹配

成功 `data`：

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

排序：`updated_at` 降序（最近更新在前）。

### 3.3 详情 `POST /getById`

权限：当前团队任意成员

请求体：

```json
{
  "id": 1
}
```

成功：`data` 为单条知识库详情（字段同列表项）。

错误：不存在或不属于当前团队 → `404`，「知识库不存在」

### 3.4 修改 `POST /update`

权限：`admin`、`tech_lead`

请求体：

```json
{
  "id": 1,
  "name": "新名称",
  "description": "新描述"
}
```

- `id`：必填
- `name`、`description`：均可选，但至少提供一个；未传的字段保持原值
- 若修改 `name`，需校验同团队不与其他知识库重名

成功：`message` 为「更新成功」，`data` 可为 `null`

错误：

- 不存在 / 非本团队 → `404`
- 重名 → `409`
- 未提供任何可改字段 → `400`（参数校验）

### 3.5 删除 `POST /delete`

权限：`admin`、`tech_lead`

请求体：

```json
{
  "id": 1
}
```

成功：`message` 为「删除成功」，`data` 为 `null`

错误：

- 不存在 / 非本团队 → `404`
- Milvus 清理失败 → 业务错误（不删 MySQL），提示向量清理失败

## 4. 删除编排（关键路径）

```
校验权限与归属
    → vector_repo.delete_by_knowledge_base(team_id, kb_id)
    → 成功则 knowledge_repo.delete(kb)
    → 失败则抛出异常，MySQL 不变
```

Milvus 约定（与现有 `test/milvusTest.py` 骨架一致）：

- Collection：`document_chunks`
- 过滤条件：`knowledge_base_id == {id} and team_id == {team_id}`
- 使用配置中的 Milvus URI 连接

本阶段不做文档表级联删除（项目中尚无独立文档 ORM 表）；仅清向量 + 删知识库主表。

## 5. 代码改动范围

| 文件 | 变更 |
|------|------|
| `app/schemas/knowledge.py` | 新建请求/响应模型 |
| `app/routers/knowledge_bases.py` | 五个 POST + 保留 `/status`；去掉旧的 GET 列表占位或改为兼容 |
| `app/services/knowledge_service.py` | create / page / get_by_id / update / delete |
| `app/repositories/knowledge_repo.py` | CRUD、分页、按团队+名称查重 |
| `app/repositories/vector_repo.py` | 实现按知识库删除向量 |
| `app/core/config.py`、`.env.example` | `MILVUS_URI`、`MILVUS_COLLECTION` 等 |
| `app/dependencies.py` | 增加 `CurrentTeamAdminOrLead`（`current_user("admin", "tech_lead")`） |
| `app/main.py` | `include_router` 挂载知识库路由 |
| `README.md` | 补充接口说明与进度 |

分层约束不变：路由不写 SQL / 不直连 Milvus；服务编排业务；Repository 负责 MySQL / Milvus 读写。

## 6. 错误与边界

| 场景 | 行为 |
|------|------|
| 名称与同团队已有库重复 | `409` |
| ID 不存在或 team 不匹配 | 统一 `404`「知识库不存在」（不泄露跨团队存在性） |
| 无角色权限 | `403`「暂无对应角色权限」 |
| Milvus 不可用 / delete 失败 | 删除接口失败，MySQL 保留 |
| `description` 传 `null` | 更新时允许清空描述；创建时等同未填 |

## 7. 非目标（本次不做）

- 文档上传、切块、Embedding 入库
- 知识库软删除
- 跨团队查询
- 前端页面

## 8. 验收要点

1. 管理员/技术领导可创建，开发者创建返回 403  
2. 同团队重名创建返回 409  
3. 成员可分页与按 ID 查详情，只能看到本团队数据  
4. 修改至少一项字段成功；改名冲突返回 409  
5. 删除前调用 Milvus 过滤删除；Milvus 失败时 MySQL 记录仍在  
6. `/docs` 可见上述五个接口；`README` 已更新说明  
