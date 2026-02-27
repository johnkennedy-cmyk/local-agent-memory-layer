"""Embedding service - supports both Ollama (local) and OpenAI."""

from typing import List
import ollama
import tiktoken

from src.config import config
from src.metrics import timed_call


class EmbeddingService:
    """Service for generating text embeddings using Ollama (local) or OpenAI."""

    _instance = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Use Ollama for embeddings (local, no API key needed)
        self.use_ollama = True
        self.ollama_model = config.ollama.embedding_model
        self.dimensions = config.ollama.embedding_dimensions

        # Fallback to OpenAI if configured
        if config.openai.api_key and config.openai.api_key != "your-openai-api-key-here":  # pragma: allowlist secret
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=config.openai.api_key)
                self.openai_model = config.openai.embedding_model
                self.use_ollama = False
                self.dimensions = config.openai.embedding_dimensions
                print(f"Using OpenAI for embeddings: {self.openai_model}")
            except Exception:
                pass

        if self.use_ollama:
            print(f"Using Ollama for embeddings: {self.ollama_model}")

        # Token counting (works for both)
        self.encoder = tiktoken.get_encoding("cl100k_base")

        # Simple cache for recent embeddings
        self._cache: dict[int, List[float]] = {}
        self._cache_max_size = 1000
        self._initialized = True

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def generate(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        # Check cache
        cache_key = hash(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.use_ollama:
            embedding = self._generate_ollama(text)
        else:
            embedding = self._generate_openai(text)

        # Cache result
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = embedding

        return embedding

    def _generate_ollama(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        tokens = self.count_tokens(text)
        with timed_call("embedding", "generate", tokens_in=tokens):
            response = ollama.embeddings(
                model=self.ollama_model,
                prompt=text
            )
        return response["embedding"]

    def _generate_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        tokens = self.count_tokens(text)
        with timed_call("embedding", "generate_openai", tokens_in=tokens):
            response = self.openai_client.embeddings.create(
                model=self.openai_model,
                input=text
            )
        return response.data[0].embedding

    def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Check cache for each text
        uncached_indices = []
        uncached_texts = []
        results: List[List[float] | None] = [None] * len(texts)

        for i, text in enumerate(texts):
            cache_key = hash(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # Generate embeddings for uncached texts
        if uncached_texts:
            if self.use_ollama:
                # Ollama doesn't support batch, so generate one by one
                for idx, text in zip(uncached_indices, uncached_texts):
                    embedding = self._generate_ollama(text)
                    results[idx] = embedding
                    cache_key = hash(text)
                    if len(self._cache) < self._cache_max_size:
                        self._cache[cache_key] = embedding
            else:
                # OpenAI supports batch
                response = self.openai_client.embeddings.create(
                    model=self.openai_model,
                    input=uncached_texts
                )
                for idx, embedding_data in zip(uncached_indices, response.data):
                    embedding = embedding_data.embedding
                    results[idx] = embedding
                    cache_key = hash(texts[idx])
                    if len(self._cache) < self._cache_max_size:
                        self._cache[cache_key] = embedding

        return results  # type: ignore


# Singleton instance
embedding_service = EmbeddingService()
