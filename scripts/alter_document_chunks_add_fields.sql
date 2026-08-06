-- 兼容已有 document_chunks 表：补齐切片业务字段
-- 可重复执行：已存在的列会跳过（需 MySQL 8+ 手工判断，或直接执行下面分步语句）

-- 1) 新增列（若报 Duplicate column 可忽略该条）
ALTER TABLE document_chunks
  ADD COLUMN chunk_id VARCHAR(128) NULL COMMENT '业务切块ID，如 101_0' AFTER id;

ALTER TABLE document_chunks
  ADD COLUMN knowledge_base_id BIGINT NULL COMMENT '所属知识库' AFTER content;

ALTER TABLE document_chunks
  ADD COLUMN team_id BIGINT NULL COMMENT '团队隔离' AFTER knowledge_base_id;

-- 2) 给 collection_name 补默认值，避免新插入时必填失败
ALTER TABLE document_chunks
  MODIFY COLUMN collection_name VARCHAR(100) NOT NULL DEFAULT 'document_chunks'
  COMMENT '对应的 Milvus 集合名';

-- 3) 回填已有数据
UPDATE document_chunks dc
INNER JOIN documents d ON d.id = dc.document_id
INNER JOIN knowledge_bases kb ON kb.id = d.knowledge_base_id
SET
  dc.chunk_id = CONCAT(dc.document_id, '_', dc.chunk_index),
  dc.knowledge_base_id = d.knowledge_base_id,
  dc.team_id = kb.team_id
WHERE dc.chunk_id IS NULL
   OR dc.knowledge_base_id IS NULL
   OR dc.team_id IS NULL;

-- 4) 改为非空（回填后执行）
ALTER TABLE document_chunks
  MODIFY COLUMN chunk_id VARCHAR(128) NOT NULL COMMENT '业务切块ID，如 101_0';

ALTER TABLE document_chunks
  MODIFY COLUMN knowledge_base_id BIGINT NOT NULL COMMENT '所属知识库';

ALTER TABLE document_chunks
  MODIFY COLUMN team_id BIGINT NOT NULL COMMENT '团队隔离';

-- 5) 索引（若已存在会报错，可忽略）
CREATE UNIQUE INDEX uk_document_chunk_id ON document_chunks (chunk_id);
CREATE INDEX idx_document_chunks_kb_id ON document_chunks (knowledge_base_id);
CREATE INDEX idx_document_chunks_team_id ON document_chunks (team_id);
