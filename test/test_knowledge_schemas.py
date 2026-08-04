"""知识库 Schema 校验。"""

import pytest
from pydantic import ValidationError

from app.schemas.knowledge import KnowledgeUpdateRequest


def test_update_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        KnowledgeUpdateRequest(id=1)


def test_update_allows_description_null():
    body = KnowledgeUpdateRequest(id=1, description=None)
    assert "description" in body.model_fields_set
    assert body.description is None


def test_update_name_only():
    body = KnowledgeUpdateRequest(id=1, name="新名称")
    assert body.name == "新名称"
