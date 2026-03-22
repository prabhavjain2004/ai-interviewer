# 🔒 Security Guide - API Key Management

## ⚠️ CRITICAL: Your API Key Was Leaked

Your Gemini API key was found in your public GitHub repository and has been automatically revoked by Google.

**Leaked Key:** `AIzaSyBOwnYjaVCpmfmWFHu31pwcn0j55urth5c`

## 🚨 Immediate Actions Required

### 1. Get a New API Key
1. Go to https://aistudio.google.com/app/apikey
2. Delete the leaked key (if still visible)
3. Create a new API key
4. Copy the new key

### 2. Update Your Local Environment
```bash
# Edit .env file
GEMINI_API_KEY=your_new_key_here
```

### 3. Clean Up Git History

Your API key is in your Git history. You need to remove it:

```bash
# Option 1: Use BFG Repo-Cleaner (recommended)
# Download from: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --replace-text passwords.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Option 2: Use git filter-branch (more complex)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch test_single.py test_two_turns.py test_activity_end_alone.py" \
  --prune-empty --tag-name-filter cat -- --all

# Force push to GitHub (WARNING: This rewrites history)
git push origin --force --all
```

### 4. Verify GitHub Repository

Check your GitHub repository and ensure:
- [ ] No test files with hardcoded keys exist
- [ ] `.env` is in `.gitignore`
- [ ] No API keys in any committed files
- [ ] Git history is cleaned

## ✅ Current Security Status

### Protected Files (in .gitignore)
- ✅ `.env` - Contains your API key (NEVER commit this)
- ✅ `__pycache__/` - Python cache files
- ✅ `data/resumes/` - User data

### Safe Files (no secrets)
- ✅ `.env.example` - Template with placeholder
- ✅ All Python source files - Use environment variables
- ✅ Documentation files - No secrets

### Removed Files
- ❌ `test_single.py` - Contained hardcoded API key (DELETED)
- ❌ `test_two_turns.py` - Contained hardcoded API key (DELETED)
- ❌ `test_activity_end_alone.py` - Contained hardcoded API key (DELETED)

## 🛡️ Security Best Practices

### 1. NEVER Hardcode API Keys

❌ **BAD:**
```python
os.environ["GEMINI_API_KEY"] = "AIzaSy..."
api_key = "AIzaSy..."
```

✅ **GOOD:**
```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
```

### 2. Use .env Files Properly

```bash
# .env (NEVER commit this)
GEMINI_API_KEY=your_actual_key_here

# .env.example (Safe to commit)
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Check .gitignore

Ensure `.gitignore` contains:
```
.env
.env.local
*.key
*.pem
secrets/
```

### 4. Scan Before Committing

```bash
# Install git-secrets
brew install git-secrets  # macOS
# or
apt-get install git-secrets  # Linux

# Set up git-secrets
git secrets --install
git secrets --register-aws
git secrets --add 'AIza[0-9A-Za-z_-]{35}'  # Gemini API key pattern

# Scan repository
git secrets --scan
```

### 5. Use GitHub Secret Scanning

GitHub automatically scans for leaked secrets. Enable it:
1. Go to your repo Settings
2. Security & analysis
3. Enable "Secret scanning"
4. Enable "Push protection"

### 6. Rotate Keys Regularly

- Rotate API keys every 90 days
- Immediately rotate if:
  - Key is accidentally committed
  - Team member leaves
  - Suspicious activity detected

## 🔍 How to Check for Leaked Keys

### Search Your Codebase
```bash
# Search for API key patterns
grep -r "AIza" .
grep -r "api_key.*=" .
grep -r "GEMINI_API_KEY.*=" .

# Search Git history
git log -p | grep "AIza"
```

### Use Online Tools
- GitHub Secret Scanning (automatic)
- GitGuardian (https://www.gitguardian.com/)
- TruffleHog (https://github.com/trufflesecurity/trufflehog)

## 📋 Security Checklist

Before every commit:
- [ ] No API keys in code
- [ ] `.env` is in `.gitignore`
- [ ] No secrets in test files
- [ ] No secrets in documentation
- [ ] No secrets in comments
- [ ] Run `git secrets --scan`

Before pushing to GitHub:
- [ ] Review all changed files
- [ ] Check for accidentally staged `.env`
- [ ] Verify no secrets in commit messages
- [ ] Run security scan

## 🚨 If You Leak a Key

1. **Immediately revoke the key** at https://aistudio.google.com/app/apikey
2. **Create a new key**
3. **Update your `.env` file**
4. **Clean Git history** (see above)
5. **Force push to GitHub** (if key was pushed)
6. **Monitor for unauthorized usage**

## 📞 Support

If you suspect unauthorized API usage:
- Check usage at: https://aistudio.google.com/app/apikey
- Contact Google Cloud Support
- Review billing for unexpected charges

## 🎓 Learn More

- [Google API Key Best Practices](https://cloud.google.com/docs/authentication/api-keys)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP API Security](https://owasp.org/www-project-api-security/)

---

**Remember:** API keys are like passwords. Treat them with the same level of security!
