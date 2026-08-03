"""通用 SQL 工具函数。"""


def wrap_count_sql(data_sql: str) -> str:
    """将数据查询 SQL 包装为 COUNT 子查询。"""
    return f"SELECT COUNT(*) FROM ({data_sql}) AS counted"