# GitHub Personal Access Token Setup Guide

This guide will help you create a personal access token (PAT) and clone the repository for use with Claude Code CLI.

## Step 1: Create a Fine-Grained Personal Access Token (Recommended)

Fine-grained tokens are more secure because they only grant access to specific repositories.

1. Go to: https://github.com/settings/personal-access-tokens/new
2. Fill in the token details:
   - **Token name**: "Claude Code - analyze-performance"
   - **Expiration**: Choose your preferred expiration (90 days recommended)
   - **Description**: Optional - e.g., "For Claude Code CLI access"
3. **Repository access**: Select **"Only select repositories"**
   - Click the dropdown and choose: `icscript/analyze-performance`
4. **Permissions** → **Repository permissions**:
   - **Contents**: Read and write (required for push/pull)
   - **Pull requests**: Read and write (if you'll create PRs)
   - **Workflows**: Read and write (if you have GitHub Actions)
   - **Metadata**: Read-only (automatically selected)
5. Click **"Generate token"** at the bottom
6. **IMPORTANT**: Copy the token immediately - you won't be able to see it again!

### Alternative: Classic Personal Access Token (All Repositories)

If you need access to multiple repositories or prefer the classic approach:

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Give your token a descriptive name (e.g., "Claude Code CLI Access")
4. Set an expiration (recommended: 90 days or custom)
5. Select the following scopes:
   - ✅ **repo** (Full control of private repositories)
   - ✅ **workflow** (Update GitHub Action workflows)
6. Click **"Generate token"** at the bottom
7. **IMPORTANT**: Copy the token immediately - you won't be able to see it again!

## Step 2: Authenticate with GitHub CLI

Choose one of these methods:

### Option A: Interactive Login (Recommended)
```bash
gh auth login
```
Follow the prompts:
- Choose "GitHub.com"
- Choose "HTTPS"
- When asked "Authenticate Git with your GitHub credentials?", choose "Yes"
- Choose "Paste an authentication token"
- Paste your PAT when prompted

### Option B: Environment Variable
```bash
export GH_TOKEN=your_token_here
gh auth status
```

To make it permanent, add to your `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export GH_TOKEN=your_token_here' >> ~/.bashrc
source ~/.bashrc
```

## Step 3: Clone the Repository

```bash
# Navigate to where you want to clone the repo
cd ~/projects  # or wherever you prefer

# Clone using GitHub CLI
gh repo clone icscript/analyze-performance

# Navigate into the repository
cd analyze-performance
```

### Alternative: Clone with Git directly
```bash
# Using HTTPS with token
git clone https://your_token_here@github.com/icscript/analyze-performance.git

# Or configure git credential helper
git clone https://github.com/icscript/analyze-performance.git
# When prompted for username: enter your GitHub username
# When prompted for password: paste your PAT
```

## Step 4: Configure Git Credentials (Optional but Recommended)

To avoid entering your token repeatedly:

```bash
# For Linux
git config --global credential.helper store

# For macOS
git config --global credential.helper osxkeychain

# For Windows
git config --global credential.helper wincred
```

Then do a git operation (like `git pull`) once and enter your credentials - they'll be saved.

## Step 5: Run Claude Code CLI

```bash
# Make sure you're in the repository directory
cd ~/projects/analyze-performance  # adjust path as needed

# Run Claude Code with teleport session
claude --teleport session_XXXXXX
```

## Troubleshooting

### "You must run claude from a checkout"
- Ensure you're inside the cloned repository directory
- Verify the git remote is set correctly: `git remote -v`

### "Authentication failed"
- Check token hasn't expired: `gh auth status`
- Verify token has correct scopes
- Try re-authenticating: `gh auth refresh`

### "Could not resolve host"
- Check internet connection
- Try using git directly instead of gh CLI

### Token Security Tips
- Never commit tokens to repositories
- Use environment variables or credential managers
- Rotate tokens regularly
- Use fine-grained PATs for better security (Settings → Developer settings → Fine-grained tokens)

## Quick Reference Commands

```bash
# Check gh auth status
gh auth status

# List your repositories
gh repo list

# Check git remote configuration
git remote -v

# Verify you're in a git repository
git status

# Pull latest changes
git pull origin main
```

---

**Created**: 2025-11-19
**Repository**: icscript/analyze-performance
**Token Type**: Fine-grained (repository-specific) recommended
