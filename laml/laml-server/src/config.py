"""Configuration management for LAML server."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class FireboltConfig:
    """Firebolt connection configuration."""
    account_name: str
    client_id: str
    client_secret: str
    database: str
    engine: str
    # Firebolt Core (local) settings
    use_core: bool = False
    core_url: str = "http://localhost:3473"


@dataclass
class OpenAIConfig:
    """OpenAI configuration."""
    api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o-mini"  # For augmentation tasks


@dataclass
class OllamaConfig:
    """Ollama configuration."""
    host: str
    model: str  # For classification/chat
    embedding_model: str = "nomic-embed-text"  # For embeddings
    embedding_dimensions: int = 768  # nomic-embed-text dimensions


@dataclass
class ElasticConfig:
    """Elasticsearch connection configuration (for vector backend=elastic)."""
    url: str
    api_key: str
    username: str
    password: str
    index_name: str
    sessions_index: str
    working_memory_index: str
    ssl_verify: bool = True
    # Embedding dimension must match Ollama/OpenAI embedding model (e.g. 768 for nomic)
    embedding_dimensions: int = 768


@dataclass
class ClickHouseConfig:
    """ClickHouse connection configuration (for vector backend=clickhouse)."""
    host: str
    port: int
    database: str
    user: str
    password: str
    table_name: str
    sessions_table: str
    working_memory_table: str
    embedding_dimensions: int = 768


@dataclass
class TurbopufferConfig:
    """Turbopuffer configuration (for vector backend=turbopuffer)."""
    api_key: str
    region: str
    base_url: str
    long_term_namespace: str
    sessions_namespace: str
    working_memory_namespace: str
    embedding_dimensions: int = 768


@dataclass
class Config:
    """Main configuration container."""
    firebolt: FireboltConfig
    openai: OpenAIConfig
    ollama: OllamaConfig
    elastic: ElasticConfig
    clickhouse: ClickHouseConfig
    turbopuffer: TurbopufferConfig

    # Vector backend: "firebolt", "elastic", "clickhouse", or "turbopuffer"
    vector_backend: str = "firebolt"
    # Optional write mirroring backend, used during migration/cutover.
    # Reads continue to use vector_backend.
    dual_write_backend: str = ""

    # Memory defaults
    default_max_tokens: int = 8000
    default_similarity_threshold: float = 0.7
    default_importance: float = 0.5


def load_config() -> Config:
    """Load configuration from environment variables."""

    firebolt = FireboltConfig(
        account_name=os.getenv("FIREBOLT_ACCOUNT_NAME", ""),
        client_id=os.getenv("FIREBOLT_CLIENT_ID", ""),
        client_secret=os.getenv("FIREBOLT_CLIENT_SECRET", ""),
        database=os.getenv("FIREBOLT_DATABASE", ""),
        engine=os.getenv("FIREBOLT_ENGINE", ""),
        use_core=os.getenv("FIREBOLT_USE_CORE", "false").lower() == "true",
        core_url=os.getenv("FIREBOLT_CORE_URL", "http://localhost:3473"),
    )

    openai = OpenAIConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )

    ollama = OllamaConfig(
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "llama3:8b"),
        embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        embedding_dimensions=int(os.getenv("OLLAMA_EMBEDDING_DIMENSIONS", "768")),
    )

    vector_backend = (os.getenv("LAML_VECTOR_BACKEND", "firebolt") or "firebolt").strip().lower()
    if vector_backend not in ("firebolt", "elastic", "clickhouse", "turbopuffer"):
        vector_backend = "firebolt"
    dual_write_backend = (os.getenv("LAML_DUAL_WRITE_BACKEND", "") or "").strip().lower()
    if dual_write_backend not in ("", "firebolt", "elastic", "clickhouse", "turbopuffer"):
        dual_write_backend = ""
    if dual_write_backend == vector_backend:
        dual_write_backend = ""

    elastic = ElasticConfig(
        url=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
        api_key=os.getenv("ELASTICSEARCH_API_KEY", ""),
        username=os.getenv("ELASTICSEARCH_USERNAME", ""),
        password=os.getenv("ELASTICSEARCH_PASSWORD", ""),
        index_name=os.getenv("ELASTICSEARCH_INDEX", "laml_long_term_memories"),
        sessions_index=os.getenv("ELASTICSEARCH_SESSIONS_INDEX", "laml_sessions"),
        working_memory_index=os.getenv("ELASTICSEARCH_WORKING_MEMORY_INDEX", "laml_working_memory"),
        ssl_verify=os.getenv("ELASTICSEARCH_SSL_VERIFY", "true").lower() == "true",
        embedding_dimensions=int(
            os.getenv("ELASTICSEARCH_EMBEDDING_DIMENSIONS")
            or os.getenv("OLLAMA_EMBEDDING_DIMENSIONS", "768")
        ),
    )

    clickhouse = ClickHouseConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        database=os.getenv("CLICKHOUSE_DATABASE", "laml"),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        table_name=os.getenv("CLICKHOUSE_TABLE", "long_term_memories"),
        sessions_table=os.getenv("CLICKHOUSE_SESSIONS_TABLE", "session_contexts"),
        working_memory_table=os.getenv("CLICKHOUSE_WORKING_MEMORY_TABLE", "working_memory_items"),
        embedding_dimensions=int(
            os.getenv("CLICKHOUSE_EMBEDDING_DIMENSIONS")
            or os.getenv("OLLAMA_EMBEDDING_DIMENSIONS", "768")
        ),
    )
    tpuf_region = os.getenv("TURBOPUFFER_REGION", "gcp-us-central1")
    turbopuffer = TurbopufferConfig(
        api_key=os.getenv("TURBOPUFFER_API_KEY", ""),
        region=tpuf_region,
        base_url=os.getenv("TURBOPUFFER_BASE_URL", f"https://{tpuf_region}.turbopuffer.com"),
        long_term_namespace=os.getenv("TURBOPUFFER_LONG_TERM_NAMESPACE", "laml_long_term_memories"),
        sessions_namespace=os.getenv("TURBOPUFFER_SESSIONS_NAMESPACE", "laml_sessions"),
        working_memory_namespace=os.getenv("TURBOPUFFER_WORKING_MEMORY_NAMESPACE", "laml_working_memory"),
        embedding_dimensions=int(
            os.getenv("TURBOPUFFER_EMBEDDING_DIMENSIONS")
            or os.getenv("OLLAMA_EMBEDDING_DIMENSIONS", "768")
        ),
    )

    return Config(
        firebolt=firebolt,
        openai=openai,
        ollama=ollama,
        elastic=elastic,
        clickhouse=clickhouse,
        turbopuffer=turbopuffer,
        vector_backend=vector_backend,
        dual_write_backend=dual_write_backend,
    )


# Global config instance
config = load_config()
