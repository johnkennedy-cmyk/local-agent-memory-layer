"""Ollama local LLM service for classification and summarization."""

import json
from typing import List, Optional
from dataclasses import dataclass
import ollama

from src.config import config
from src.metrics import timed_call


@dataclass
class MemoryClassification:
    """Result of memory classification."""
    memory_category: str  # 'episodic', 'semantic', 'procedural', 'preference'
    memory_subtype: str
    importance: float
    entities: List[str]
    is_temporal: bool
    summary: Optional[str] = None


class OllamaService:
    """Service for local LLM operations using Ollama."""

    _instance = None

    def __new__(cls) -> "OllamaService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.host = config.ollama.host
        self.model = config.ollama.model
        self._client = ollama.Client(host=self.host)
        self._initialized = True

    def _chat(self, prompt: str, system: Optional[str] = None, operation: str = "chat") -> str:
        """Send a chat message to Ollama."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Estimate input tokens (rough approximation: 4 chars per token)
        input_chars = len(prompt) + (len(system) if system else 0)
        est_tokens_in = input_chars // 4

        with timed_call("ollama", operation, tokens_in=est_tokens_in) as tc:
            response = self._client.chat(
                model=self.model,
                messages=messages
            )
            content = response["message"]["content"]
            tc.tokens_out = len(content) // 4  # Estimate output tokens

        return content

    def _extract_json(self, text: str, default: dict) -> dict:
        """Extract JSON from LLM response."""
        try:
            # Try to find JSON in the response
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass
        return default

    def _extract_json_array(self, text: str) -> List[str]:
        """Extract JSON array from LLM response."""
        try:
            json_start = text.find('[')
            json_end = text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass
        return []

    def classify_memory(self, content: str, context: str = "") -> MemoryClassification:
        """
        Classify content into memory taxonomy.
        Uses local LLM to determine category, subtype, importance, and entities.
        """
        system_prompt = """You are a memory classification system. Analyze the given content and classify it for storage in a long-term memory system.

Return ONLY valid JSON with these fields:
- memory_category: one of 'episodic', 'semantic', 'procedural', 'preference'
- memory_subtype:
  - For episodic: 'event', 'decision', 'conversation', 'outcome'
  - For semantic: 'user', 'project', 'environment', 'domain', 'entity'
  - For procedural: 'workflow', 'pattern', 'tool_usage', 'debugging'
  - For preference: 'communication', 'style', 'tools', 'boundaries'
- importance: float 0.0 to 1.0 (how likely to be needed again)
- entities: array of named entities in format "type:name" (e.g., "database:prod_db", "table:users", "file:api.py")
- is_temporal: boolean (is this time-sensitive information?)
- summary: optional shorter version (only if content is long)"""

        prompt = f"""Content to classify:
{content}

Additional context:
{context if context else "None provided"}

Return JSON only, no explanation."""

        response = self._chat(prompt, system_prompt, operation="classify")

        data = self._extract_json(response, {
            "memory_category": "semantic",
            "memory_subtype": "domain",
            "importance": 0.5,
            "entities": [],
            "is_temporal": False,
        })

        return MemoryClassification(
            memory_category=data.get("memory_category", "semantic"),
            memory_subtype=data.get("memory_subtype", "domain"),
            importance=float(data.get("importance", 0.5)),
            entities=data.get("entities", []),
            is_temporal=data.get("is_temporal", False),
            summary=data.get("summary"),
        )

    def extract_entities(self, content: str) -> List[str]:
        """Extract named entities from content."""
        system_prompt = """Extract named entities from the content. Return a JSON array of strings in the format "type:name".

Entity types to look for:
- database: database names
- table: table/collection names
- field: column/field names
- file: file paths
- function: function/method names
- class: class names
- api: API endpoints
- service: service names
- person: people's names
- tool: tools/frameworks
- concept: technical concepts

Return ONLY a JSON array, no explanation."""

        response = self._chat(f"Content:\n{content}", system_prompt, operation="extract_entities")
        return self._extract_json_array(response)

    def summarize(self, content: str, max_words: int = 100) -> str:
        """Summarize content to fit within token limit."""
        system_prompt = """You are a precise summarization assistant.
Your ONLY job is to summarize the text given to you.
Return ONLY JSON in this exact format: {"summary": "your summary here"}
Do NOT include anything else. Do NOT make up content. Do NOT add questions or code."""

        prompt = f"""Summarize this text in {max_words} words or less:

"{content}"

Return JSON: {{"summary": "..."}}"""

        response = self._chat(prompt, system_prompt, operation="summarize")

        # Try to extract JSON
        result = self._extract_json(response, {"summary": content[:200]})
        summary = result.get("summary", "")

        # If summary is empty or looks like garbage, use first 200 chars of content
        if not summary or len(summary) < 10 or "```" in summary:
            # Fallback: just truncate the content
            summary = content[:200].strip()
            if len(content) > 200:
                summary += "..."

        return summary

    def detect_query_intent(self, query: str) -> str:
        """Detect the intent of a user query for retrieval optimization."""
        system_prompt = """Classify the query intent. Return ONLY one of these words:
- how_to: asking how to do something
- what_happened: asking about past events/decisions
- what_is: asking for facts/information
- debug: asking for help with an error/problem
- general: other/unclear

Return only the classification word, nothing else."""

        response = self._chat(query, system_prompt, operation="detect_intent")

        intent = response.strip().lower().replace('"', '').replace("'", "")
        valid_intents = ["how_to", "what_happened", "what_is", "debug", "general"]

        # Handle common variations
        if "how" in intent:
            return "how_to"
        if "what_happened" in intent or "happened" in intent:
            return "what_happened"
        if "what_is" in intent or "what is" in intent:
            return "what_is"
        if "debug" in intent:
            return "debug"

        return intent if intent in valid_intents else "general"

    def generate_hypothetical_questions(self, content: str) -> List[str]:
        """Generate hypothetical questions someone might ask to retrieve this memory."""
        system_prompt = """Generate 3-5 short questions that someone might ask which this content would answer.
These questions help with semantic search retrieval.

Return ONLY a JSON array of question strings, nothing else.
Keep questions short and natural.

Examples for "Jon lives in Washington state":
["Where does Jon live?", "What state is Jon in?", "Jon's location?"]"""

        prompt = f"""Content:
{content}

Return JSON array of questions only:"""

        response = self._chat(prompt, system_prompt, operation="hypothetical_questions")
        questions = self._extract_json_array(response)

        # Filter out any garbage - questions should be short and end with ?
        valid_questions = [
            q for q in questions
            if isinstance(q, str) and len(q) < 100 and ("?" in q or len(q.split()) < 8)
        ]

        return valid_questions[:5]  # Max 5 questions


# Singleton instance
ollama_service = OllamaService()
