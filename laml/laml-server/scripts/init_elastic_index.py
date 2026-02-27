#!/usr/bin/env python3
"""Create or ensure the LAML long-term memory Elasticsearch index exists with correct mapping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config


def get_elasticsearch_client():
    """Build Elasticsearch client from config."""
    from elasticsearch import Elasticsearch

    es_config = config.elastic
    kwargs = {
        "hosts": [es_config.url],
        "verify_certs": es_config.ssl_verify,
    }
    if es_config.api_key:
        kwargs["api_key"] = es_config.api_key
    elif es_config.username and es_config.password:
        kwargs["basic_auth"] = (es_config.username, es_config.password)
    return Elasticsearch(**kwargs)


def build_index_body(dimension: int) -> dict:
    """Build index mapping and settings for laml_long_term_memories."""
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "memory_id": {"type": "keyword"},
                "user_id": {"type": "keyword"},
                "org_id": {"type": "keyword"},
                "memory_category": {"type": "keyword"},
                "memory_subtype": {"type": "keyword"},
                "content": {"type": "text"},
                "summary": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": dimension,
                    "index": True,
                    "similarity": "cosine",
                },
                "entities": {"type": "keyword"},
                "metadata": {"type": "text", "index": False},
                "event_time": {"type": "date"},
                "is_temporal": {"type": "boolean"},
                "importance": {"type": "float"},
                "access_count": {"type": "integer"},
                "decay_factor": {"type": "float"},
                "supersedes": {"type": "keyword"},
                "source_session": {"type": "keyword"},
                "source_type": {"type": "keyword"},
                "confidence": {"type": "float"},
                "created_at": {"type": "date"},
                "last_accessed": {"type": "date"},
                "updated_at": {"type": "date"},
                "deleted_at": {"type": "date"},
            }
        },
    }


def main():
    print("LAML - Init Elasticsearch index for long-term memory")
    print("=" * 50)
    if config.vector_backend != "elastic":
        print("LAML_VECTOR_BACKEND is not 'elastic'; skipping index creation.")
        print("Set LAML_VECTOR_BACKEND=elastic and ELASTICSEARCH_* vars to use Elastic.")
        return 0

    client = get_elasticsearch_client()
    index_name = config.elastic.index_name
    dimension = config.elastic.embedding_dimensions

    if client.indices.exists(index=index_name):
        print(f"Index '{index_name}' already exists.")
        return 0

    body = build_index_body(dimension)
    client.indices.create(index=index_name, body=body)
    print(f"Created index '{index_name}' with dense_vector dimension={dimension}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
