#!/bin/bash
# Security setup script for new projects
# Usage: ./scripts/setup-security.sh

set -e

echo "🔒 Setting up security for this repository..."

# Check if git-secrets is installed
if ! command -v git-secrets &> /dev/null; then
    echo "⚠️  git-secrets not found. Installing..."
    brew install git-secrets
fi

# Install git-secrets hooks
echo "📦 Installing git-secrets hooks..."
git secrets --install

# Register AWS patterns
git secrets --register-aws

# Add custom patterns
echo "🔍 Adding credential patterns..."
git secrets --add 'FIREBOLT_CLIENT_SECRET\s*=\s*[^=]'
git secrets --add 'OPENAI_API_KEY\s*=\s*[^=]'
git secrets --add 'password\s*=\s*[^=]'
git secrets --add 'secret\s*=\s*[^=]'
git secrets --add 'api_key\s*=\s*[^=]'
git secrets --add 'client_secret\s*=\s*[^=]'
git secrets --add 'sk-[A-Za-z0-9]{32,}'
git secrets --add 'ghp_[A-Za-z0-9]{36}'
git secrets --add 'AKIA[0-9A-Z]{16}'

# Allow template files
echo "✅ Adding allowed patterns..."
git secrets --add --allowed '\.env\.example'
git secrets --add --allowed 'your-.*-here'
git secrets --add --allowed 'your-.*-name'
git secrets --add --allowed 'your-.*-id'

# Check if pre-commit is available
if command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit hooks..."
    pre-commit install
    
    if [ -f ".pre-commit-config.yaml" ]; then
        echo "✅ Pre-commit configuration found"
    else
        echo "⚠️  .pre-commit-config.yaml not found. Create one using the template."
    fi
else
    echo "⚠️  pre-commit not found. Install with: pip install pre-commit detect-secrets"
fi

# Create secrets baseline if detect-secrets is available
if command -v detect-secrets &> /dev/null; then
    echo "🔍 Creating secrets baseline..."
    detect-secrets scan > .secrets.baseline 2>&1 || echo "{}" > .secrets.baseline
    echo "✅ Secrets baseline created"
fi

echo ""
echo "✅ Security setup complete!"
echo ""
echo "Next steps:"
echo "1. Review .gitignore to ensure all credential patterns are excluded"
echo "2. Create .env.example template (never commit .env)"
echo "3. Test with: git secrets --scan"
echo "4. Test pre-commit: pre-commit run --all-files"
