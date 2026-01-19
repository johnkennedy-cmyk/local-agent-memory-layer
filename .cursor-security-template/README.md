# Security Template for New Projects

This template provides a consistent security posture for all new projects.

## Quick Setup

Run the setup script:
```bash
./scripts/setup-security.sh
```

Or manually:

1. **Copy .gitignore** to your project root
2. **Copy .pre-commit-config.yaml** to your project root
3. **Install git-secrets**:
   ```bash
   brew install git-secrets
   git secrets --install
   git secrets --register-aws
   # Add custom patterns (see setup-security.sh)
   ```
4. **Install pre-commit**:
   ```bash
   pip install pre-commit detect-secrets
   pre-commit install
   detect-secrets scan --baseline .secrets.baseline .
   ```

## Security Rules

- ✅ NEVER hardcode credentials
- ✅ ALWAYS use environment variables
- ✅ NEVER commit .env files
- ✅ ALWAYS use .env.example as template
- ✅ ALWAYS review git diff before committing

## Files Included

- `.gitignore` - Comprehensive credential protection
- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `scripts/setup-security.sh` - Automated setup script
