# from pymilvus import MilvusClient, DataType
#
# # 连接 Milvus 服务
# client = MilvusClient(uri="http://localhost:19530")
#
# # 定义 Collection Schema
# schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
# schema.add_field("id", DataType.INT64, is_primary=True)
# schema.add_field("vector", DataType.FLOAT_VECTOR, dim=1536)  # 与百炼 Embedding 维度对齐
# schema.add_field("chunk_text", DataType.VARCHAR, max_length=8192)  # 切块原始文本
# schema.add_field("document_id", DataType.INT64)  # 关联 MySQL 文档表
# schema.add_field("knowledge_base_id", DataType.INT64)  # 所属知识库
# schema.add_field("team_id", DataType.INT64)  # 团队隔离标识
#
# # 配置向量索引参数
# index_params = client.prepare_index_params()
# index_params.add_index(
#     field_name="vector",
#     index_type="AUTOINDEX",  # Milvus 自动选择最优索引类型
#     metric_type="COSINE",  # 余弦相似度，适合文本语义检索
# )
#
# # 创建 Collection（自动加载）
# client.create_collection(
#     collection_name="document_chunks",
#     schema=schema,
#     index_params=index_params,
# )
#
# # 插入切块向量数据
# data = [
#     {
#         "vector": embedding_vector,  # 百炼 Embedding 模型输出的 1536 维向量
#         "chunk_text": "FastAPI 使用 Depends 实现依赖注入...",
#         "document_id": 101,
#         "knowledge_base_id": 5,
#         "team_id": 2,
#     },
# ]
# client.insert(collection_name="document_chunks", data=data)
#
# # 语义检索：按团队隔离 + Top-K 召回
# results = client.search(
#     collection_name="document_chunks",
#     data=[query_embedding],  # 用户提问的向量化结果
#     limit=5,  # 召回 Top 5 最相关切块
#     filter='team_id == 2',  # 团队级数据隔离过滤条件
#     output_fields=["chunk_text", "document_id"],  # 返回切块文本和文档 ID
# )


from pymilvus import connections

# 尝试连接到本地的 Milvus 服务
try:
    connections.connect(alias="default", uri="http://localhost:19530")
    print("成功连接到 Milvus 服务！")
except Exception as e:
    print(f"连接失败: {e}")