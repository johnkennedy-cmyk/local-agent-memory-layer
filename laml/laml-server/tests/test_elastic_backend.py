"""Tests for Elastic vector store and memory repository (with mocked Elasticsearch)."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_es_client():
    """Mock Elasticsearch client for unit tests."""
    client = MagicMock()
    # search response shape
    client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "mem-1",
                    "_score": 0.92,
                    "_source": {
                        "memory_id": "mem-1",
                        "user_id": "user1",
                        "memory_category": "semantic",
                        "memory_subtype": "domain",
                        "importance": 0.7,
                        "created_at": "2025-01-01T00:00:00Z",
                    },
                },
            ]
        }
    }
    client.count.return_value = {"count": 1}
    client.get.return_value = {"found": True, "_source": {"user_id": "user1"}, "_id": "mem-1"}
    # Use a real dict so get_many_by_ids iteration and _source work correctly
    client.mget.return_value = {
        "docs": [
            {
                "found": True,
                "_id": "mem-1",
                "_source": {
                    "memory_id": "mem-1",
                    "user_id": "user1",
                    "content": "test content",
                    "summary": "test",
                    "memory_category": "semantic",
                    "memory_subtype": "domain",
                    "entities": [],
                    "importance": 0.7,
                    "access_count": 0,
                    "created_at": "2025-01-01T00:00:00Z",
                    "metadata": None,
                },
            }
        ]
    }
    client.index.return_value = {"result": "created"}
    client.update.return_value = {"result": "updated"}
    client.delete.return_value = {"result": "deleted"}
    client.delete_by_query.return_value = {"deleted": 1}
    client.indices.exists.return_value = False
    return client


@patch("src.memory.elastic_vector_store._get_es_client")
@patch("src.memory.elastic_vector_store.config")
def test_elastic_vector_store_search(mock_config, mock_get_client, mock_es_client):
    """ElasticVectorStore.search returns VectorSearchResult list from kNN response."""
    mock_get_client.return_value = mock_es_client
    mock_config.elastic.index_name = "laml_long_term_memories"

    from src.memory.elastic_vector_store import ElasticVectorStore

    store = ElasticVectorStore()
    results = store.search([0.1] * 768, top_k=5, filters={"user_id": "user1"})

    assert len(results) == 1
    assert results[0].memory_id == "mem-1"
    assert results[0].score == 0.92
    assert results[0].metadata["user_id"] == "user1"
    mock_es_client.search.assert_called_once()


@patch("src.memory.elastic_memory_repo._get_es_client")
@patch("src.memory.elastic_memory_repo.config")
def test_elastic_memory_repo_count_for_user(mock_config, mock_get_client, mock_es_client):
    """ElasticMemoryRepository.count_for_user returns count from ES count API."""
    mock_get_client.return_value = mock_es_client
    mock_config.elastic.index_name = "laml_long_term_memories"

    from src.memory.elastic_memory_repo import ElasticMemoryRepository

    repo = ElasticMemoryRepository()
    n = repo.count_for_user("user1", include_deleted=False)
    assert n == 1
    mock_es_client.count.assert_called_once()


@patch("src.memory.elastic_memory_repo._get_es_client")
@patch("src.memory.elastic_memory_repo.config")
def test_elastic_memory_repo_get_many_by_ids(mock_config, mock_get_client, mock_es_client):
    """ElasticMemoryRepository.get_many_by_ids returns list of doc dicts."""
    mock_get_client.return_value = mock_es_client
    mock_config.elastic.index_name = "laml_long_term_memories"

    from src.memory.elastic_memory_repo import ElasticMemoryRepository

    repo = ElasticMemoryRepository()
    rows = repo.get_many_by_ids(["mem-1"], user_id="user1")
    assert len(rows) == 1
    assert rows[0]["memory_id"] == "mem-1"
    assert rows[0]["content"] == "test content"
    mock_es_client.mget.assert_called_once()
