#!/usr/bin/env python3
"""Test script for security validation module."""

import sys
sys.path.insert(0, "/Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server")

from src.security import (
    validate_content_for_storage,
    detect_sensitive_content,
    redact_sensitive_content,
    looks_like_api_key
)


def test_api_key_detection():
    """Test detection of various API key formats."""
    print("\n=== Testing API Key Detection ===\n")
    
    test_cases = [
        # (content, should_block, description)
        ("sk-1234567890abcdefghijklmnop", True, "OpenAI API key"),
        ("sk-proj-abc123def456-xyz789_test_key", True, "OpenAI project key"),
        ("ghp_1234567890abcdefghijklmnopqrstuvwxyz12", True, "GitHub PAT"),
        ("AKIAIOSFODNN7EXAMPLE", True, "AWS Access Key"),
        ("AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe", True, "Google API Key"),
        ("sk-ant-api03-abcdef123456", True, "Anthropic API Key"),
        ("The API key format is sk-xxxx", False, "Mention of format (no actual key)"),
        ("Use your OpenAI key from the dashboard", False, "Safe reference"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:50]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_password_detection():
    """Test detection of password patterns."""
    print("\n=== Testing Password Detection ===\n")
    
    test_cases = [
        ('password = "mysecretpassword123"', True, "Password assignment"),
        ('PASSWORD: SuperSecret!@#', True, "Password with colon"),
        ("mysql://user:secretpass123@localhost:3306/db", True, "DB connection string"),
        ("The password field should be encrypted", False, "Safe discussion"),
        ("Reset your password via email", False, "Safe instruction"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:60]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_token_detection():
    """Test detection of various token formats."""
    print("\n=== Testing Token Detection ===\n")
    
    test_cases = [
        ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", 
         True, "Bearer token with JWT"),
        ("Authorization: Bearer abc123def456ghi789jkl012mno345", True, "Auth header"),
        ("xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx", True, "Slack token"),
        ("Use bearer token authentication", False, "Safe discussion"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Content: {content[:60]}...")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_private_key_detection():
    """Test detection of private keys."""
    print("\n=== Testing Private Key Detection ===\n")
    
    test_cases = [
        ("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...", True, "Private key"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow...", True, "RSA private key"),
        ("Generate a private key using openssl", False, "Safe instruction"),
    ]
    
    passed = 0
    failed = 0
    
    for content, should_block, desc in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        blocked = not is_safe
        
        if blocked == should_block:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status}: {desc}")
        print(f"   Expected block: {should_block}, Actual block: {blocked}")
        if violations:
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_safe_content():
    """Test that safe content is allowed."""
    print("\n=== Testing Safe Content (should NOT block) ===\n")
    
    test_cases = [
        "The user prefers dark mode for their IDE",
        "Remember to use semantic versioning for releases",
        "The database schema has a users table with id, email, created_at columns",
        "Firebolt Core runs on port 3473",
        "Use environment variables for configuration",
        "The API endpoint is /api/v1/memories",
        "Python 3.14 is recommended for this project",
    ]
    
    passed = 0
    failed = 0
    
    for content in test_cases:
        is_safe, error_msg, violations = validate_content_for_storage(content)
        
        if is_safe:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL (false positive)"
            failed += 1
        
        print(f"{status}: {content[:60]}...")
        if not is_safe:
            print(f"   Error: {error_msg}")
            print(f"   Violations: {[v.pattern_name for v in violations]}")
        print()
    
    return passed, failed


def test_redaction():
    """Test content redaction functionality."""
    print("\n=== Testing Content Redaction ===\n")
    
    content = "Use API key sk-1234567890abcdefghijklmnop and token ghp_abcdef123456789012345678901234567890"
    redacted = redact_sensitive_content(content)
    
    print(f"Original: {content}")
    print(f"Redacted: {redacted}")
    
    # Check that sensitive patterns are removed
    if "sk-1234" not in redacted and "ghp_" not in redacted:
        print("✅ PASS: Sensitive content was redacted")
        return 1, 0
    else:
        print("❌ FAIL: Sensitive content was not fully redacted")
        return 0, 1


def main():
    """Run all security tests."""
    print("=" * 60)
    print("FML Security Validation Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    results = [
        test_api_key_detection(),
        test_password_detection(),
        test_token_detection(),
        test_private_key_detection(),
        test_safe_content(),
        test_redaction(),
    ]
    
    for passed, failed in results:
        total_passed += passed
        total_failed += failed
    
    print("=" * 60)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    if total_failed > 0:
        print("\n⚠️  Some tests failed - review the security patterns")
        return 1
    else:
        print("\n✅ All security tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
