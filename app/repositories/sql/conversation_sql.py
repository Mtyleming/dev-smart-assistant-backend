"""对话模块手写 SQL。"""

# 普通成员：仅查本人对话
LIST_MINE_DATA_SQL = """
SELECT
    c.id,
    c.title,
    c.mode,
    c.user_id,
    c.team_id,
    c.created_at,
    c.updated_at,
    c.is_delete
FROM conversations c
WHERE c.team_id = :team_id
  AND c.is_delete = 0
  AND c.user_id = :user_id
  AND (:title IS NULL OR c.title LIKE :title)
  AND (:mode IS NULL OR c.mode = :mode)
"""

# 团队管理员：查当前团队全部对话
LIST_TEAM_DATA_SQL = """
SELECT
    c.id,
    c.title,
    c.mode,
    c.user_id,
    c.team_id,
    c.created_at,
    c.updated_at,
    c.is_delete,
    u.username
FROM conversations c
INNER JOIN users u ON c.user_id = u.id
WHERE c.team_id = :team_id
  AND c.is_delete = 0
  AND (:title IS NULL OR c.title LIKE :title)
  AND (:mode IS NULL OR c.mode = :mode)
  AND (:username IS NULL OR u.username LIKE :username)
"""

LIST_CONVERSATION_PAGINATION_SQL = """
ORDER BY c.updated_at DESC
LIMIT :limit OFFSET :offset
"""
