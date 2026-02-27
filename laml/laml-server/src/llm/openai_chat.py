"""OpenAI chat service for augmentation tasks."""

import json
from typing import List, Optional
from openai import OpenAI

from src.config import config


class OpenAIChatService:
    """Service for augmentation tasks using OpenAI chat models."""

    _instance = None

    def __new__(cls) -> "OpenAIChatService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.client = OpenAI(api_key=config.openai.api_key)
        self.model = config.openai.chat_model
        self._initialized = True

    def _chat(self, prompt: str, system: Optional[str] = None) -> str:
        """Send a chat message to OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content or ""

    def _extract_json_array(self, text: str) -> List[str]:
        """Extract JSON array from response."""
        try:
            json_start = text.find('[')
            json_end = text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            pass
        return []

    def generate_hypothetical_questions(self, content: str) -> List[str]:
        """Generate hypothetical questions someone might ask to retrieve this memory."""
        system_prompt = """You generate short questions that someone might naturally ask which would be answered by the given content.
These questions are used for semantic search retrieval.
Return ONLY a JSON array of 3-5 question strings.
Keep questions short, natural, and varied in phrasing."""

        prompt = f"""Content:
{content}

Generate 3-5 short questions that this content would answer.
Return only a JSON array like: ["Question 1?", "Question 2?", "Question 3?"]"""

        response = self._chat(prompt, system_prompt)
        questions = self._extract_json_array(response)

        # Filter out any garbage
        valid_questions = [
            q for q in questions
            if isinstance(q, str) and len(q) < 150 and len(q) > 5
        ]

        return valid_questions[:5]

    def summarize(self, content: str, max_words: int = 50) -> str:
        """Summarize content concisely."""
        system_prompt = f"""Summarize the given content in {max_words} words or less.
Return ONLY the summary text, nothing else.
Be concise and preserve key facts."""

        response = self._chat(f"Summarize:\n{content}", system_prompt)

        # Clean up response
        summary = response.strip()
        if not summary:
            summary = content[:200] + ("..." if len(content) > 200 else "")

        return summary


# Singleton instance
openai_chat_service = OpenAIChatService()
