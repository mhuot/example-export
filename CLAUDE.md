# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Python scripts to export swim meet data from Swimtopia's API (maestro.swimtopia.com). Developed by analyzing HAR file captures of the web application's API usage. Uses simplified OAuth2 password grant authentication (no client credentials required). Exports data in HY3 format compatible with HyTek Meet Manager.

## Development Environment Setup

### Virtual Environment (Always Required)
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration
```bash
# Copy example config and edit with credentials
cp config.example.json config.json
# Edit config.json with username/password (Swimtopia login credentials)
```

## Running the Scripts

### Usage
```bash
# List available meets (to find meet IDs)
python swimtopia_export.py --list-meets

# With config file
python swimtopia_export.py

# Override meet ID
python swimtopia_export.py -m 12345

# Change export type (result, advancers, merge-entries, merge-results)
python swimtopia_export.py -t advancers

# List existing exports without creating new one
python swimtopia_export.py --list-only
```

## Code Quality Requirements

All Python code must comply with:
- **pylint**: No linting errors
- **black**: Code formatting
- **Descriptive variable names**: Always use clear, meaningful names

### Running Code Quality Tools
```bash
# Install tools (in venv)
pip install pylint black

# Format code with black
black swimtopia_*.py

# Check linting
pylint swimtopia_*.py
```

## High-Level Architecture

### Authentication Flow (Simplified OAuth2)
- **No client_id or client_secret needed** - uses password grant flow
- Endpoint: `POST https://api.swimtopia.org/oauth/token`
- Only requires username (email) and password - same as web login
- Returns bearer token for subsequent API requests

### Export Workflow (Client-Side UUID Pattern)
1. **Client generates UUID** - Unique task ID created before API call (unusual pattern)
2. **Create task** - `POST /v3/meets/{meet_id}/export-tasks` with client-generated UUID
3. **Poll status** - `GET /v3/meets/{meet_id}/export-tasks/{task_id}` until `currentState` = "completed"
4. **Download** - Use `exportHref` URL (Rails Active Storage signed URL)

### SwimtopiaExporter Class Structure
```python
class SwimtopiaExporter:
  def authenticate(username, password) -> bool
  def list_meets(account_id=None) -> list              # NEW: List available meets
  def create_export_task(meet_id, export_type, ...) -> task_id
  def poll_export_status(meet_id, task_id, ...) -> task_data
  def download_export(export_url, output_dir) -> filepath
  def list_export_tasks(meet_id) -> list
```

### API Specification
- Base URL: `https://api.swimtopia.org`
- Version: v3
- Content-Type: `application/vnd.api+json` (JSON API spec)
- Export formats: HY3 (HyTek compatible)
- Export types: "result", "advancers", "merge-entries", "merge-results"
- Processing time: Typically < 1 second

## File Descriptions

- **swimtopia_export.py** - Main export script with all features (config file, CLI arguments, list meets/tasks, create/download exports)
- **config.json** - Configuration file with credentials (gitignored, not committed)
- **config.example.json** - Template for users to copy
- **dev_cache_api.py** - Development tool to cache API responses (gitignored, not committed)

## Common Issues & Solutions

1. **JSON parse error on config**: Remove comments from JSON files
2. **Authentication fails**: Check email/password, no client_id needed
3. **Export timeout**: Increase `max_poll_attempts` in config
4. **SSL errors**: Set `verify_ssl: false` in config (not recommended)

## Development Notes

### What We Learned from HAR Analysis
- 56 API requests to api.swimtopia.org in typical session
- Heavy use of OPTIONS preflight (CORS)
- Filter parameters: `filter[account_id]`, `filter[session_id]`
- Include parameters for eager loading: `include=teams,sessions,heats`
- Export tasks maintain history (can list previous exports)

### API Endpoints Discovered
```
/oauth/token                                 # Authentication
/v3/ping                                     # Health check
/v3/users/current                            # Current user info
/v3/accounts                                 # Account information
/v3/meets                                    # List meets
/v3/meets/{id}                              # Meet details
/v3/meets/{id}/current_user_authority       # User permissions for meet
/v3/meets/{id}/athletes                     # Athletes in meet
/v3/meets/{id}/events                       # Events in meet
/v3/meets/{id}/events/{id}                  # Specific event details
/v3/meets/{id}/event-nodes                  # Event hierarchy/structure
/v3/meets/{id}/divisions                    # Age divisions
/v3/meets/{id}/school-year-groups           # School year groupings
/v3/meets/{id}/team-groupings               # Team groupings
/v3/meets/{id}/team-standings               # Team scores/standings
/v3/meets/{id}/meet-time-standards          # Time standards for meet
/v3/meets/{id}/record-sets                  # Records (pool, team, etc.)
/v3/meets/{id}/dq-options                   # Disqualification codes
/v3/meets/{id}/export-tasks                 # Create/list export tasks
/v3/meets/{id}/export-tasks/{uuid}          # Check export task status
/v3/meets/{id}/export-results-tasks         # Alternative export endpoint
```

### Query Parameters Discovered
- **filter[account_id]** - Filter meets by account
- **filter[session_id]** - Filter events by session
- **filter[id]** - Filter by specific IDs
- **include** - Eager load related resources (e.g., "teams,sessions,heats")

### Response Times from HAR
- Export task creation: ~194ms
- Status polling: ~170ms
- Task completion: < 1 second
- Largest operations: Events with related data ~400-450ms

## Future Enhancements

### Potential Features
- [ ] Batch export multiple meets
- [ ] Resume interrupted downloads
- [ ] Parse HY3 files after download
- [ ] Convert HY3 to other formats
- [ ] Automatic retry on network errors
- [ ] Progress bar for large downloads
- [ ] Export specific teams/sessions (currently all)
- [ ] Support for other Swimtopia endpoints

### Known Limitations
- No refresh token handling (token expiry not tested)
- Limited error messages from API
- No support for export-results-tasks endpoint (purpose unknown)
- Team/session filters hardcoded to -1 (all)

## Context for Future Claude Sessions

If working on this project again:
1. User has working Swimtopia credentials (no API keys needed)
2. Meet ID 12345 is the example from captured data
3. HY3 format is for HyTek Meet Manager compatibility
4. User is looking for alternatives to HyTek/CTS timing systems
5. Export files are zip archives containing HY3 data
6. Authentication is simpler than standard OAuth - no client registration

## Testing Checklist

- [ ] Authentication with valid credentials
- [ ] Authentication with invalid credentials
- [ ] Export task creation
- [ ] Polling until completion
- [ ] Download of export file
- [ ] Config file parsing
- [ ] Command line argument handling
- [ ] Network error handling
- [ ] Timeout handling

## Related Context

User (Mike) works with:
- Swimming competition timing (CTS Gen 7 equipment)
- Meet Manager software
- Looking for alternatives to HyTek
- Interested in Swimtopia/Meet Maestro as alternatives

## Code Quality Notes

- Uses standard requests library (no async needed due to simple workflow)
- Follows Python naming conventions
- Includes comprehensive error handling
- Progress feedback for user
- Configurable timeouts and retry logic
- Clean separation of concerns in enhanced version

## Development Best Practices

### PEP 8 Compliance
The code follows PEP 8 Python style guidelines:
- **Function names**: `snake_case` (e.g., `authenticate()`, `create_export_task()`)
- **Class names**: `PascalCase` (e.g., `SwimtopiaExporter`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `USERNAME`, `MEET_ID`)
- **Line length**: Kept under 100 characters for readability
- **Imports**: Standard library first, then third-party (requests)
- **Docstrings**: Triple quotes with description and Args/Returns sections
- **Spacing**: 2 blank lines between top-level functions/classes

To check PEP 8 compliance:
```bash
pip install flake8
flake8 swimtopia_*.py --max-line-length=100
```

### Git Workflow with Atomic Commits
Structure commits to be atomic - each commit does ONE thing:

```bash
# Initial setup
git init
git add README.md requirements.txt .gitignore
git commit -m "Initial project setup with dependencies"

# Add authentication
git add swimtopia_export.py
git commit -m "Add OAuth authentication function"

# Add export creation
git add swimtopia_export.py
git commit -m "Add export task creation with client-side UUID"

# Add polling logic
git add swimtopia_export.py
git commit -m "Add status polling with timeout handling"

# Add download functionality
git add swimtopia_export.py
git commit -m "Add file download with progress indicator"

# Add configuration support
git add config.example.json
git commit -m "Add configuration file template"

# Add CLI arguments support
git add swimtopia_export.py
git commit -m "Add CLI arguments and config file support"

# Documentation updates
git add CLAUDE.md
git commit -m "Add Claude context documentation"

# Bug fixes should be separate
git add swimtopia_export.py
git commit -m "Fix JSON parsing error in config loader"
```

### .gitignore File
Essential for keeping sensitive data out of version control:

```gitignore
# Virtual Environment
venv/
env/
.venv/

# Configuration with credentials
config.json
*.json
!config.example.json

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Exports directory
exports/
*.zip
*.hy3

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Environment variables
.env
```

### Code Review Checklist
Before committing:
- [ ] Run flake8 for style violations
- [ ] Test with valid and invalid credentials
- [ ] Verify no hardcoded credentials
- [ ] Check error messages are user-friendly
- [ ] Ensure config.json is in .gitignore
- [ ] Update README if functionality changed
- [ ] Write descriptive commit message

### Dependency Management
Keep dependencies minimal and documented:
```bash
# requirements.txt
requests>=2.31.0  # For API calls

# requirements-dev.txt (optional)
flake8>=6.0.0     # Code style checker
pytest>=7.0.0     # Testing framework
black>=23.0.0     # Code formatter
```

### Testing Structure (Future Enhancement)
```python
# test_swimtopia_export.py
import pytest
from unittest.mock import Mock, patch
from swimtopia_export import SwimtopiaExporter

def test_authentication_success():
    """Test successful authentication"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'test_token'
        }
        
        exporter = SwimtopiaExporter()
        result = exporter.authenticate('user@example.com', 'password')
        
        assert result == True
        assert exporter.access_token == 'test_token'

def test_authentication_failure():
    """Test authentication with wrong credentials"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 401
        
        exporter = SwimtopiaExporter()
        result = exporter.authenticate('wrong@example.com', 'wrong')
        
        assert result == False
        assert exporter.access_token is None
```

## Questions for User (if revisiting)

1. Do you need to handle token refresh for long sessions?
2. Want to parse/convert the HY3 files after download?
3. Need to filter by specific teams or sessions?
4. Should we handle multiple meets in one run?
5. Any specific error conditions to handle?

---
*Created: November 2024*
*HAR file analyzed: maestro_swimtopia_com.har*
*API version: v3*
