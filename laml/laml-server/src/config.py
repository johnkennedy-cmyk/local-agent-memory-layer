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
class Config:
    """Main configuration container."""
    firebolt: FireboltConfig
    openai: OpenAIConfig
    ollama: OllamaConfig

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

    return Config(
        firebolt=firebolt,
        openai=openai,
        ollama=ollama,
    )


# Global config instance
config = load_config()
