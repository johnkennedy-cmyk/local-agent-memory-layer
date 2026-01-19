"""Memory taxonomy definitions aligned with human cognition."""

from enum import Enum
from typing import Dict


class MemoryCategory(str, Enum):
    """Top-level memory categories."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PREFERENCE = "preference"


class EpisodicSubtype(str, Enum):
    """Subtypes for episodic memory (what happened)."""
    EVENT = "event"
    DECISION = "decision"
    CONVERSATION = "conversation"
    OUTCOME = "outcome"


class SemanticSubtype(str, Enum):
    """Subtypes for semantic memory (facts & knowledge)."""
    USER = "user"
    PROJECT = "project"
    ENVIRONMENT = "environment"
    DOMAIN = "domain"
    ENTITY = "entity"


class ProceduralSubtype(str, Enum):
    """Subtypes for procedural memory (how to do things)."""
    WORKFLOW = "workflow"
    PATTERN = "pattern"
    TOOL_USAGE = "tool_usage"
    DEBUGGING = "debugging"


class PreferenceSubtype(str, Enum):
    """Subtypes for preference memory (learned behaviors)."""
    COMMUNICATION = "communication"
    STYLE = "style"
    TOOLS = "tools"
    BOUNDARIES = "boundaries"


# Mapping of categories to their valid subtypes
CATEGORY_SUBTYPES: Dict[str, list] = {
    MemoryCategory.EPISODIC: [e.value for e in EpisodicSubtype],
    MemoryCategory.SEMANTIC: [e.value for e in SemanticSubtype],
    MemoryCategory.PROCEDURAL: [e.value for e in ProceduralSubtype],
    MemoryCategory.PREFERENCE: [e.value for e in PreferenceSubtype],
}


# Retrieval weight profiles based on query intent
INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    "how_to": {
        "working_memory": 0.25,
        "procedural.workflow": 0.25,
        "procedural.pattern": 0.15,
        "semantic.project": 0.15,
        "semantic.entity": 0.10,
        "preference.style": 0.05,
        "episodic.decision": 0.05,
    },
    "what_happened": {
        "working_memory": 0.20,
        "episodic.decision": 0.30,
        "episodic.event": 0.20,
        "episodic.outcome": 0.15,
        "semantic.project": 0.10,
        "episodic.conversation": 0.05,
    },
    "what_is": {
        "working_memory": 0.20,
        "semantic.entity": 0.30,
        "semantic.project": 0.20,
        "semantic.domain": 0.15,
        "semantic.environment": 0.10,
        "episodic.decision": 0.05,
    },
    "debug": {
        "working_memory": 0.30,
        "procedural.debugging": 0.25,
        "episodic.outcome": 0.20,
        "semantic.environment": 0.10,
        "semantic.entity": 0.10,
        "preference.tools": 0.05,
    },
    "general": {
        "working_memory": 0.35,
        "semantic.project": 0.15,
        "episodic.decision": 0.15,
        "semantic.entity": 0.10,
        "procedural.workflow": 0.10,
        "preference.communication": 0.10,
        "semantic.user": 0.05,
    },
}


def get_retrieval_weights(intent: str) -> Dict[str, float]:
    """Get retrieval weights for a query intent."""
    return INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["general"])


def validate_subtype(category: str, subtype: str) -> bool:
    """Validate that subtype is valid for category."""
    valid_subtypes = CATEGORY_SUBTYPES.get(category, [])
    return subtype in valid_subtypes


def get_all_subtypes() -> Dict[str, list]:
    """Get all categories and their subtypes."""
    return CATEGORY_SUBTYPES.copy()
