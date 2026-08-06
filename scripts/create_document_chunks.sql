-- 文档切块表：存切片原文（向量仍在 Milvus collection document_chunks）
CREATE TABLE IF NOT EXISTS document_chunks (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  chunk_id VARCHAR(128) NOT NULL COMMENT '业务切块ID，如 101_0',
  document_id BIGINT NOT NULL COMMENT '关联 documents.id',
  chunk_index BIGINT NOT NULL COMMENT '切块序号，从 0 起',
  content LONGTEXT NOT NULL COMMENT '切块原文',
  knowledge_base_id BIGINT NOT NULL COMMENT '所属知识库',
  team_id BIGINT NOT NULL COMMENT '团队隔离',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_document_chunk_id (chunk_id),
  UNIQUE KEY uk_document_chunk_index (document_id, chunk_index),
  KEY idx_document_chunks_document_id (document_id),
  KEY idx_document_chunks_kb_id (knowledge_base_id),
  KEY idx_document_chunks_team_id (team_id),
  CONSTRAINT fk_document_chunks_document
    FOREIGN KEY (document_id) REFERENCES documents (id),
  CONSTRAINT fk_document_chunks_kb
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id),
  CONSTRAINT fk_document_chunks_team
    FOREIGN KEY (team_id) REFERENCES teams (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档切块原文';
