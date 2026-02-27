"""Security validation for FML memory storage.

This module provides programmatic checks to prevent storing sensitive
data like API keys, passwords, and tokens in the memory database.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SecurityViolation:
    """Represents a detected security violation."""
    pattern_name: str
    matched_text: str  # Redacted version
    severity: str  # 'critical', 'high', 'medium'
    description: str


# Patterns for detecting sensitive data
# Each tuple: (name, regex_pattern, severity, description)
SENSITIVE_PATTERNS: List[Tuple[str, str, str, str]] = [
    # API Keys
    (
        "OpenAI API Key",
        r"sk-[a-zA-Z0-9]{20,}",
        "critical",
        "OpenAI API key detected"
    ),
    (
        "OpenAI Project Key",
        r"sk-proj-[a-zA-Z0-9\-_]{20,}",
        "critical",
        "OpenAI project API key detected"
    ),
    (
        "GitHub Token",
        r"ghp_[a-zA-Z0-9]{36,}",
        "critical",
        "GitHub personal access token detected"
    ),
    (
        "GitHub OAuth Token",
        r"gho_[a-zA-Z0-9]{36,}",
        "critical",
        "GitHub OAuth token detected"
    ),
    (
        "GitHub App Token",
        r"ghu_[a-zA-Z0-9]{36,}",
        "critical",
        "GitHub user-to-server token detected"
    ),
    (
        "AWS Access Key",
        r"AKIA[A-Z0-9]{16}",
        "critical",
        "AWS access key ID detected"
    ),
    (
        "AWS Secret Key",
        r"(?i)aws.{0,20}secret.{0,20}['\"][a-zA-Z0-9/+=]{40}['\"]",
        "critical",
        "AWS secret access key detected"
    ),
    (
        "Slack Token",
        r"xox[baprs]-[a-zA-Z0-9\-]{10,}",
        "critical",
        "Slack token detected"
    ),
    (
        "Stripe Key",
        r"sk_live_[a-zA-Z0-9]{24,}",
        "critical",
        "Stripe live secret key detected"
    ),
    (
        "Stripe Test Key",
        r"sk_test_[a-zA-Z0-9]{24,}",
        "high",
        "Stripe test secret key detected"
    ),
    (
        "Google API Key",
        r"AIza[a-zA-Z0-9\-_]{35}",
        "critical",
        "Google API key detected"
    ),
    (
        "Anthropic API Key",
        r"sk-ant-[a-zA-Z0-9\-_]{10,}",
        "critical",
        "Anthropic API key detected"
    ),

    # Bearer Tokens
    (
        "Bearer Token",
        r"(?i)bearer\s+[a-zA-Z0-9\-_\.]{20,}",
        "critical",
        "Bearer token detected"
    ),
    (
        "Authorization Header",
        r"(?i)authorization['\"]?\s*[:=]\s*['\"]?bearer\s+[a-zA-Z0-9\-_\.]+",
        "critical",
        "Authorization header with bearer token detected"
    ),

    # Private Keys
    (
        "Private Key",
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        "critical",
        "Private key detected"
    ),
    (
        "PGP Private Key",
        r"-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----",
        "critical",
        "PGP private key detected"
    ),

    # Passwords
    (
        "Password Assignment",
        r"(?i)password\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        "high",
        "Password assignment detected"
    ),
    (
        "Password Value",
        r"(?i)(password|passwd|pwd)\s*[=:]\s*[^\s'\"]{8,}",
        "high",
        "Password value detected"
    ),
    (
        "Password in URL",
        r"(?i)://[^:]+:[^@]{8,}@",
        "high",
        "Password in URL detected"
    ),
    (
        "Database Connection String",
        r"(?i)(mysql|postgres|postgresql|mongodb|redis)://[^:]+:[^@]+@",
        "high",
        "Database connection string with credentials detected"
    ),

    # .env file patterns
    (
        "Env File Content",
        r"(?m)^[A-Z_]{2,}=\S{20,}$",
        "medium",
        "Environment variable assignment detected (possible .env content)"
    ),
    (
        "Secret Assignment",
        r"(?i)(secret|token|apikey|api_key|password|passwd|pwd)\s*[=:]\s*['\"]?[a-zA-Z0-9\-_]{16,}",
        "high",
        "Secret/token assignment detected"
    ),

    # JWT Tokens
    (
        "JWT Token",
        r"eyJ[a-zA-Z0-9\-_]+\.eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+",
        "high",
        "JWT token detected"
    ),

    # Firebolt specific
    (
        "Firebolt Client Secret",
        r"(?i)firebolt.{0,20}(client_secret|secret)\s*[=:]\s*['\"]?[a-zA-Z0-9\-_]{20,}",
        "critical",
        "Firebolt client secret detected"
    ),
]

# Compile patterns for efficiency
_COMPILED_PATTERNS = [
    (name, re.compile(pattern), severity, desc)
    for name, pattern, severity, desc in SENSITIVE_PATTERNS
]


def detect_sensitive_content(content: str) -> List[SecurityViolation]:
    """
    Scan content for sensitive data patterns.

    Args:
        content: The text content to scan

    Returns:
        List of SecurityViolation objects for each detected issue
    """
    violations = []

    for name, pattern, severity, description in _COMPILED_PATTERNS:
        matches = pattern.findall(content)
        for match in matches:
            # Redact the matched text for logging (show first/last few chars)
            if isinstance(match, tuple):
                match = match[0]  # Handle groups

            if len(match) > 12:
                redacted = f"{match[:4]}...{match[-4:]}"
            else:
                redacted = "[REDACTED]"

            violations.append(SecurityViolation(
                pattern_name=name,
                matched_text=redacted,
                severity=severity,
                description=description
            ))

    return violations


def validate_content_for_storage(content: str) -> Tuple[bool, Optional[str], List[SecurityViolation]]:
    """
    Validate content before storing in memory.

    Args:
        content: The content to validate

    Returns:
        Tuple of (is_safe, error_message, violations)
        - is_safe: True if content can be stored
        - error_message: Human-readable error if not safe
        - violations: List of detected violations
    """
    violations = detect_sensitive_content(content)

    if not violations:
        return True, None, []

    # Check for critical violations (always block)
    critical = [v for v in violations if v.severity == "critical"]
    high = [v for v in violations if v.severity == "high"]

    if critical:
        error_msg = (
            f"SECURITY BLOCK: Content contains {len(critical)} critical security violation(s). "
            f"Detected: {', '.join(v.pattern_name for v in critical)}. "
            "Sensitive data like API keys, tokens, and private keys cannot be stored in memory."
        )
        return False, error_msg, violations

    if high:
        error_msg = (
            f"SECURITY WARNING: Content contains {len(high)} high-severity security issue(s). "
            f"Detected: {', '.join(v.pattern_name for v in high)}. "
            "This content appears to contain credentials or secrets and has been blocked."
        )
        return False, error_msg, violations

    # Medium severity - allow but warn (could be false positives)
    return True, None, violations


def redact_sensitive_content(content: str) -> str:
    """
    Redact sensitive patterns from content.

    This can be used as an alternative to blocking - replace
    sensitive data with [REDACTED] markers.

    Args:
        content: The content to redact

    Returns:
        Content with sensitive patterns replaced
    """
    redacted = content

    for name, pattern, severity, _ in _COMPILED_PATTERNS:
        if severity in ("critical", "high"):
            redacted = pattern.sub(f"[REDACTED-{name.upper().replace(' ', '-')}]", redacted)

    return redacted


# Quick check functions for specific patterns
def looks_like_api_key(text: str) -> bool:
    """Quick check if text looks like an API key."""
    api_key_patterns = [
        r"^sk-[a-zA-Z0-9]{20,}$",
        r"^ghp_[a-zA-Z0-9]{36,}$",
        r"^AKIA[A-Z0-9]{16}$",
        r"^sk_live_[a-zA-Z0-9]{24,}$",
        r"^AIza[a-zA-Z0-9\-_]{35}$",
    ]
    return any(re.match(p, text) for p in api_key_patterns)


def looks_like_password(text: str) -> bool:
    """Quick check if text looks like a password field value."""
    # Common password field patterns
    if re.match(r"(?i)^(password|passwd|pwd|secret|token)$", text):
        return False  # These are field names, not values

    # Check for password-like assignments
    return bool(re.search(r"(?i)password\s*[=:]\s*\S+", text))
