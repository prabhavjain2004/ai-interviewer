# Contributing to AI Interviewer & Mentor

First off, thank you for considering contributing to AI Interviewer & Mentor! It's people like you that make this project a great tool for developers worldwide.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Project Structure](#project-structure)
- [Testing Guidelines](#testing-guidelines)

---

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Pledge

We are committed to making participation in this project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

---

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (code snippets, screenshots, logs)
- **Describe the behavior you observed** and what you expected
- **Include your environment details** (OS, Python version, browser)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description** of the proposed feature
- **Explain why this enhancement would be useful**
- **Include mockups or examples** if applicable

### Your First Code Contribution

Unsure where to begin? Look for issues labeled:
- `good first issue` - Simple issues perfect for newcomers
- `help wanted` - Issues where we need community help
- `documentation` - Improvements to docs

### Priority Areas for Contribution

1. **Mobile Responsiveness** - Make the UI work seamlessly on phones/tablets
2. **Browser Compatibility** - Test and fix issues on Safari, Firefox, Edge
3. **WebSocket Reconnection** - Implement auto-reconnect on network drops
4. **Multi-Language Support** - Add i18n for non-English interviews
5. **Real-Time Hints** - Live coaching suggestions during interviews
6. **Analytics Dashboard** - Track metrics and user behavior
7. **Testing** - Add unit tests, integration tests, E2E tests

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A Google Gemini API key
- An Upstash Redis account (free tier works)

### Local Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-interviewer-mentor.git
   cd ai-interviewer-mentor
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Run the development server**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Open your browser**
   ```
   http://localhost:8000
   ```

### Development Tools

We recommend using:
- **VS Code** with Python extension
- **Postman** or **Thunder Client** for API testing
- **Redis Insight** for debugging Redis state
- **Chrome DevTools** for frontend debugging

---

## Pull Request Process

### Before Submitting

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the coding standards below
   - Add comments for complex logic
   - Update documentation if needed

3. **Test your changes**
   - Manually test the feature
   - Ensure no existing functionality breaks
   - Test on multiple browsers if frontend changes

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```
   
   Use conventional commit messages:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `style:` - Code style changes (formatting, etc.)
   - `refactor:` - Code refactoring
   - `test:` - Adding tests
   - `chore:` - Maintenance tasks

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

### Submitting the PR

1. Go to the original repository on GitHub
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template:
   - **Title:** Clear, descriptive title
   - **Description:** What does this PR do?
   - **Related Issues:** Link to related issues
   - **Testing:** How did you test this?
   - **Screenshots:** If UI changes, include before/after

### PR Review Process

1. A maintainer will review your PR within 48 hours
2. Address any requested changes
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release!

---

## Coding Standards

### Python Code Style

- **Follow PEP 8** - Use `black` for auto-formatting
- **Type hints** - All function signatures must have type hints
- **Docstrings** - Use Google-style docstrings for public functions
- **Async/await** - Use async for all I/O operations
- **Error handling** - Always catch specific exceptions

Example:
```python
async def generate_report(
    session_id: str,
    api_key: str,
) -> CoachReport:
    """
    Generates a coaching report for a completed interview session.

    Args:
        session_id: Unique identifier for the interview session
        api_key: Google Gemini API key

    Returns:
        CoachReport: Structured coaching report with scores and feedback

    Raises:
        ValueError: If session has no transcript or invalid data
        APIError: If Gemini API call fails
    """
    # Implementation here
```

### JavaScript Code Style

- **Use modern ES6+ syntax**
- **Avoid global variables** - Use modules or closures
- **Async/await** over callbacks
- **Clear variable names** - `sessionId` not `sid`
- **Comments for complex logic**

### File Organization

- **One class per file** (Python)
- **Group related functions** in modules
- **Keep files under 500 lines** - split if larger
- **Use meaningful file names** - `resume_parser.py` not `utils.py`

### Naming Conventions

- **Python:**
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private: `_leading_underscore`

- **JavaScript:**
  - Functions/variables: `camelCase`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`

---

## Project Structure

Understanding the codebase:

```
agents/          # Multi-agent system (Interviewer, Auditor, Coach)
api/             # FastAPI routes and WebSocket handlers
core/            # Core business logic (orchestrator, state machine)
services/        # External service clients (Redis, etc.)
templates/       # Frontend HTML/JS/CSS
prompts/         # System prompts for LLMs
Docs/            # Architecture and design docs
```

### Key Files

- `main.py` - FastAPI app entry point
- `core/orchestrator.py` - LangGraph state machine
- `core/streaming_manager.py` - Gemini Live wrapper
- `agents/interviewer.py` - Real-time interview agent
- `agents/coach.py` - Post-interview coaching agent
- `api/websocket.py` - WebSocket audio bridge

---

## Testing Guidelines

### Manual Testing Checklist

Before submitting a PR, test:

- [ ] Resume upload (PDF, TXT, MD)
- [ ] Interview start and connection
- [ ] Audio input/output works
- [ ] Camera feed displays
- [ ] Transcript updates in real-time
- [ ] Interview can be ended cleanly
- [ ] Coaching report generates
- [ ] Report displays correctly

### Browser Testing

Test on:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

### Future: Automated Testing

We plan to add:
- Unit tests with `pytest`
- Integration tests for API endpoints
- E2E tests with `playwright`
- Load testing with `locust`

---

## Documentation

### When to Update Docs

Update documentation when you:
- Add a new feature
- Change existing behavior
- Add new configuration options
- Fix a bug that was unclear in docs

### Documentation Files

- `README.md` - Main project overview
- `CONTRIBUTING.md` - This file
- `Docs/architecture.md` - System design
- `Docs/rules.md` - Development rules
- Code docstrings - Inline documentation

---

## Questions?

- **GitHub Discussions** - Ask questions, share ideas
- **GitHub Issues** - Report bugs, request features
- **Email** - Reach out to maintainers directly

---

## Recognition

Contributors will be:
- Listed in the README
- Mentioned in release notes
- Invited to the contributors team (after 3+ merged PRs)

---

Thank you for contributing! 🎉

Every contribution, no matter how small, makes this project better for developers worldwide.
