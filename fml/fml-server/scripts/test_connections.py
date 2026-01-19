#!/usr/bin/env python3
"""Test script to verify all service connections work."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config


def test_firebolt():
    """Test Firebolt connection."""
    print("\n1. Testing Firebolt connection...")
    print(f"   Account: {config.firebolt.account_name}")
    print(f"   Database: {config.firebolt.database}")
    print(f"   Engine: {config.firebolt.engine}")

    try:
        from src.db.client import db
        result = db.execute("SELECT 1 AS test")
        print(f"   ✓ Connection successful! Result: {result}")
        return True
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False


def test_embeddings():
    """Test embedding generation (Ollama or OpenAI)."""
    print("\n2. Testing Embeddings...")

    try:
        from src.llm.embeddings import embedding_service

        # Show which backend is being used
        if embedding_service.use_ollama:
            print(f"   Backend: Ollama ({embedding_service.ollama_model})")
        else:
            print(f"   Backend: OpenAI ({embedding_service.openai_model})")

        embedding = embedding_service.generate("Test embedding")
        print(f"   ✓ Embedding generated! Dimensions: {len(embedding)}")

        tokens = embedding_service.count_tokens("Hello world")
        print(f"   ✓ Token counting works! 'Hello world' = {tokens} tokens")
        return True
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False


def test_ollama():
    """Test Ollama connection."""
    print("\n3. Testing Ollama connection...")
    print(f"   Host: {config.ollama.host}")
    print(f"   Model: {config.ollama.model}")

    try:
        from src.llm.ollama import ollama_service

        # Test intent detection (simple task)
        intent = ollama_service.detect_query_intent("How do I create a table?")
        print(f"   ✓ Intent detection works! 'How do I create a table?' -> {intent}")

        # Test entity extraction
        entities = ollama_service.extract_entities(
            "The users table in the prod_db database has an email column"
        )
        print(f"   ✓ Entity extraction works! Found: {entities}")

        return True
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        print(f"   Make sure Ollama is running: ollama serve")
        print(f"   And the model is pulled: ollama pull {config.ollama.model}")
        return False


def main():
    print("=" * 60)
    print("FML Server - Connection Tests")
    print("=" * 60)

    results = {
        "Firebolt": test_firebolt(),
        "Embeddings": test_embeddings(),
        "Ollama (LLM)": test_ollama(),
    }

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

    all_passed = True
    for service, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {service}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All connections working! Ready to build.")
    else:
        print("\n⚠️  Some connections failed. Please fix before proceeding.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
