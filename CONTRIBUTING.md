# Contributing to Upcode Harbor

First off, thank you for considering contributing to Upcode Harbor! It's people like you that make Upcode Harbor such a great tool.

## 🎯 Ways to Contribute

There are many ways you can contribute to Upcode Harbor:

- 🐛 **Report Bugs** - Help us identify and fix issues
- 💡 **Suggest Features** - Share ideas for new features
- 📝 **Improve Documentation** - Help make our docs better
- 🔧 **Submit Pull Requests** - Fix bugs or add features
- 🏪 **Add App Templates** - Contribute new app store templates
- 🌍 **Translations** - Help translate Upcode Harbor to other languages

## 📋 Code of Conduct

This project and everyone participating in it is governed by respect and professionalism. Please be considerate and respectful in all interactions.

## 🐛 Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates.

When you create a bug report, include as many details as possible:

- **Clear descriptive title**
- **Steps to reproduce** the behavior
- **Expected behavior**
- **Actual behavior**
- **Screenshots** if applicable
- **Environment details:**
  - OS version
  - Python version
  - Node.js version
  - Docker version
  - Browser (for frontend issues)

**Example:**
```markdown
## Bug: Container creation fails with Docker

**Environment:**
- OS: Ubuntu 22.04
- Python: 3.10
- Docker: 24.0.7

**Steps to reproduce:**
1. Go to Containers section
2. Click "Create Container"
3. Fill in form with image "nginx:latest"
4. Click Create

**Expected:** Container should be created
**Actual:** Error message "Failed to create container"

**Logs:**
```
[error logs here]
```
```

## 💡 Suggesting Features

Feature suggestions are welcome! Please provide:

- **Clear description** of the feature
- **Use case** - Why is this feature needed?
- **Proposed solution** - How should it work?
- **Alternatives considered** - Any other approaches?

## 🔧 Pull Request Process

### Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/upcode-at/upcode-harbor.git
   cd upcode-harbor
   ```

3. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

### Development Setup

**Backend (Python/FastAPI):**
```bash
cd upservx-service
pip install -r requirements.txt
python main.py
```

**Frontend (Next.js):**
```bash
cd upservx
npm install
npm run dev
```

### Making Changes

1. **Write clean, readable code** following existing patterns
2. **Test your changes** thoroughly
3. **Update documentation** if needed
4. **Add comments** for complex logic
5. **Follow the existing code style**

### Code Style Guidelines

**Python:**
- Follow PEP 8
- Use type hints where appropriate
- Write descriptive function/variable names
- Add docstrings for functions

**TypeScript/React:**
- Use TypeScript for type safety
- Follow existing component patterns
- Use functional components with hooks
- Keep components focused and reusable

### Commit Messages

Write clear, descriptive commit messages:

```bash
# Good examples
git commit -m "feat: add firewall management with nftables"
git commit -m "fix: correct ISO count in dashboard statistics"
git commit -m "docs: update installation instructions"
git commit -m "refactor: improve container listing performance"

# Bad examples
git commit -m "fix stuff"
git commit -m "update"
git commit -m "wip"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

### Submitting Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** on GitHub with:
   - Clear title describing the change
   - Description of what changed and why
   - Reference to related issues (e.g., "Fixes #123")
   - Screenshots for UI changes
   - Testing details

3. **Respond to feedback** - Be open to suggestions and iterate on your PR

### PR Checklist

Before submitting, ensure:

- [ ] Code follows the project's code style
- [ ] Changes have been tested
- [ ] Documentation has been updated
- [ ] Commit messages are clear and descriptive
- [ ] No unnecessary files are included
- [ ] All tests pass (if applicable)
- [ ] PR description clearly explains the changes

## 🏪 Adding App Store Templates

To contribute a new app template:

1. **Create a new directory** in `app-store-templates/`:
   ```bash
   mkdir app-store-templates/your-app
   ```

2. **Create required files:**
   
   **app.json:**
   ```json
   {
     "name": "Your App",
     "description": "Brief description of your app",
     "version": "latest",
     "category": "media|database|development|tools|network",
     "icon": "🎬",
     "author": "Your Name",
     "ports": ["8080:8080"],
     "volumes": ["/opt/upservx/data/yourapp:/data"],
     "environment": {
       "PUID": "1000",
       "PGID": "1000",
       "TZ": "Europe/Vienna"
     }
   }
   ```

   **docker-compose.yml:**
   ```yaml
   version: '3.8'
   
   services:
     yourapp:
       image: yourapp/yourapp:latest
       container_name: yourapp
       restart: unless-stopped
       environment:
         - PUID=1000
         - PGID=1000
         - TZ=Europe/Vienna
       volumes:
         - /opt/upservx/data/yourapp:/data
       ports:
         - "8080:8080"
   ```

   **README.md:**
   ```markdown
   # Your App
   
   Brief description of the app.
   
   ## Features
   
   - Feature 1
   - Feature 2
   
   ## Default Port
   
   - Web UI: `3000`
   
   ## Configuration
   
   Setup instructions...
   
   ## Documentation
   
   Link to official documentation
   ```

3. **Test your template** before submitting
4. **Submit a PR** with your new template

## 🧪 Testing

Before submitting:

1. **Test manually** - Verify your changes work as expected
2. **Test edge cases** - Try unusual inputs and scenarios
3. **Test on clean install** - Ensure it works on a fresh setup
4. **Check browser console** - No errors in the console
5. **Test responsive design** - Works on mobile/tablet (for UI changes)

## 📝 Documentation

When adding features, update:

- Main README.md with feature description
- API documentation (if applicable)
- Component/function comments
- App template READMEs

## 📦 Release Management & Documentation

Upcode Harbor uses a structured approach for tracking versions, releases, and changes. Understanding this system helps maintain clear project history.

### Documentation Files Overview

The project uses several markdown files to manage releases and changes:

| File | Purpose | Updated When |
|------|---------|--------------|
| **VERSION.md** | Contains the current version number (e.g., `0.1.0`) | Every release |
| **RELEASE.md** | Release notes for the current version | Every release |
| **CHANGELOG.md** | Tracks unreleased changes for the next version | As changes are made |
| **README.md** | Project overview and documentation | As needed |
| **TODO.md** | Planned features and known issues | As needed |
| **CONTRIBUTING.md** | Contribution guidelines (this file) | As needed |

### Release Workflow

#### 1. During Development (Adding Changes)

When you make changes, document them in **CHANGELOG.md**:

```markdown
# Changelog

## Unreleased

### Added
- New feature: Automatic /etc/fstab management for mounted drives
- Support for Unmount functionality in Storage Management UI

### Fixed
- Fixed issue with container stats not updating
- Corrected API authentication for cluster nodes

### Changed
- Improved error handling in backup system
- Optimized drive listing performance

### Security
- Updated dependencies to latest versions
```

**Categories to use:**
- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Features that will be removed
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security-related changes

#### 2. Making a Release

When preparing a new release (done by maintainers):

1. **Update VERSION.md:**
   ```bash
   echo "0.2.0" > VERSION.md
   ```

2. **Move changes from CHANGELOG.md to RELEASE.md:**
   - Copy content from `## Unreleased` section in CHANGELOG.md
   - Update RELEASE.md with the new version information
   - Clear the `## Unreleased` section in CHANGELOG.md

3. **Create release in releases/ directory:**
   ```bash
   # Copy RELEASE.md to releases/
   cp RELEASE.md releases/0.2.0.md
   ```

4. **Tag the release:**
   ```bash
   git tag -a v0.2.0 -m "Release version 0.2.0"
   git push origin v0.2.0
   ```

### Example CHANGELOG.md Structure

```markdown
# Changelog

All notable changes to Upcode Harbor will be documented here.

## Unreleased

### Added
- Your new features here

### Fixed
- Your bug fixes here

## [0.1.0] - 2026-02-15

Initial release - see releases/0.1.0.md for details
```

### Contributing Changes

When submitting a pull request:

1. **Add your changes to CHANGELOG.md** under the `## Unreleased` section
2. **Use the appropriate category** (Added, Fixed, Changed, etc.)
3. **Write clear descriptions** of your changes
4. **Don't modify VERSION.md or RELEASE.md** - these are updated during release

**Example:**

```markdown
## Unreleased

### Added
- Automatic /etc/fstab management when mounting drives via Storage UI
- Unmount button for mounted drives with fstab cleanup

### Changed
- Improved fstab formatting with aligned columns
- Mount operation now uses UUID for device identification
```

### Best Practices

- ✅ **Do** add all notable changes to CHANGELOG.md
- ✅ **Do** use clear, user-facing language
- ✅ **Do** reference issue numbers when applicable
- ✅ **Do** categorize changes appropriately
- ❌ **Don't** include internal refactoring unless user-facing
- ❌ **Don't** use technical jargon without explanation
- ❌ **Don't** modify VERSION.md in pull requests

## 🤝 Community

- **GitHub Issues:** For bug reports and feature requests
- **Pull Requests:** For code contributions
- **Discussions:** For questions and general discussion

## ⚖️ License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You!

Your contributions make Upcode Harbor better for everyone. We appreciate your time and effort!

---

**Questions?** Feel free to open an issue or discussion on GitHub.

**Happy Contributing! 🚀**
