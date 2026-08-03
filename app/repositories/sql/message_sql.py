"""消息模块手写 SQL。"""

LIST_MESSAGES_DATA_SQL = """
SELECT
    m.id,
    m.conversation_id,
    m.role,
    m.content,
    m.content_type,
    m.created_at
FROM messages m
INNER JOIN conversations c ON m.conversation_id = c.id
WHERE m.conversation_id = :conversation_id
  AND c.user_id = :user_id
  AND c.team_id = :team_id
  AND c.is_delete = 0
  AND m.is_delete = 0
"""

LIST_MESSAGES_PAGINATION_SQL = """
ORDER BY m.created_at ASC
LIMIT :limit OFFSET :offset
"""
