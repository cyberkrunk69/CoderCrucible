# CoderCrucible Codebase Analysis

## 1. Overview

The repository is **CoderCrucible**, a Python CLI tool that helps users export their Claude Code conversation history to Hugging Face for use in training or fine-tuning AI models. It focuses heavily on privacy with multiple layers of PII redaction.

**Repository Location**: `/Users/vivariumenv1/GITHUBS/codercrucible/`

---

## 2. Directory Structure

```
codercrucible/
├── .claude/skills/codercrucible/SKILL.md   # Claude Code skill definition
├── .github/workflows/
│   ├── test.yml                        # CI: test on Python 3.10-3.13
│   └── publish.yml                     # CI: publish to PyPI
├── codercrucible/                           # Main package
│   ├── __init__.py                     # Version: 0.2.1
│   ├── cli.py                          # CLI interface (925 lines)
│   ├── config.py                       # Config management (49 lines)
│   ├── parser.py                       # Log parsing (293 lines)
│   ├── anonymizer.py                   # PII anonymization (106 lines)
│   └── secrets.py                       # Secret detection (249 lines)
├── tests/                              # Pytest test suite
│   ├── conftest.py                     # Fixtures
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_parser.py
│   ├── test_anonymizer.py
│   └── test_secrets.py
├── docs/SKILL.md                       # Bundled skill for agents
├── pyproject.toml                      # Package config
├── README.md                           # Full documentation
├── LICENSE                             # MIT
└── .gitignore
```

---

## 3. Technology Stack

**Language**: Python 3.10+

**Dependencies**:
- `huggingface_hub>=0.20.0` - For dataset uploads
- `pytest` (dev) - Testing

**Standard Library**: `argparse`, `json`, `re`, `pathlib`, `hashlib`, `math`, `datetime`

---

## 4. Architecture

### Design Patterns

#### 4.1 Stateful Anonymization (`anonymizer.py`)

The `Anonymizer` class maintains state for consistent username hashing across sessions. It tracks extra usernames beyond the system user to ensure the same username always maps to the same hash.

```python
class Anonymizer:
    def __init__(self, extra_usernames: list[str] = None):
        self.extra_usernames = extra_usernames or []
        # ...
```

#### 4.2 Pipeline Architecture

The export process follows a sequential pipeline:

```
discover_projects → parse_sessions → anonymize → redact_secrets → export_jsonl → push_to_hf
```

Each stage transforms the data before passing it to the next.

#### 4.3 Stage-Based Workflow (`cli.py` lines 69-147)

CoderCrucible guides users through a 4-stage workflow:

- **Stage 1 (auth)**: Hugging Face authentication check
- **Stage 2 (configure)**: Project selection and redaction configuration  
- **Stage 3 (review)**: Export locally, manual PII audit
- **Stage 4 (done)**: Successfully published to Hugging Face

---

## 5. Core Modules

### 5.1 cli.py (925 lines)

Main CLI orchestration. Entry point is `main()`.

**Commands**:

| Command | Description |
|---------|-------------|
| `codercrucible prep` | Discover projects, detect HF auth |
| `codercrucible status` | Show current stage and next steps |
| `codercrucible list` | List all projects with exclusion status |
| `codercrucible config` | View or set configuration |
| `codercrucible export` | Export and optionally push to Hugging Face |
| `codercrucible confirm` | Scan for PII, summarize export, unlock pushing |
| `codercrucible update-skill` | Install/update Claude Code skill |

**Key Functions**:

- `discover_projects()` - Scans `~/.claude/projects/` for projects
- `run_export()` - Orchestrates the full export pipeline
- `push_to_hub()` - Uploads dataset to Hugging Face
- `make_readme()` - Creates dataset card for Hugging Face
- `get_next_steps()` - Determines what the user should do next based on current stage

### 5.2 parser.py (293 lines)

Parses Claude Code session JSONL files from `~/.claude/projects/<project_name>/sessions/`.

**Key Functions**:

- `parse_conversations()` - Main parser, iterates through all session files
- `read_session_file()` - Reads a single `.jsonl` session file
- `extract_messages()` - Extracts user/assistant messages from session
- `extract_tool_calls()` - Extracts tool invocations (Read, Write, Bash, etc.)
- `extract_thinking()` - Extracts Claude's thinking (pre-tool use)

**Output Data Structure** (each line in conversations.jsonl):

```python
{
    "session_id": str,           # Unique session identifier
    "project_name": str,         # Project directory name
    "messages": [...],           # List of message objects
    "token_counts": {            # From session stats
        "input": int,
        "output": int, 
        "total": int
    },
    "duration_seconds": float,  # Session duration
    "message_count": int,       # Number of messages
    "tool_call_count": int,     # Number of tool calls
}
```

**Message Object Structure**:

```python
{
    "type": "user" | "assistant",
    "content": str,             # Message text
    "thinking": str | None,     # Claude's thinking (assistant only)
    "tool_calls": [...] | None  # Tool invocations (assistant only)
}
```

### 5.3 secrets.py (249 lines)

Detects and redacts secrets/credentials using multiple detection strategies.

**Detection Mechanisms**:

1. **Regex Pattern Matching** (20+ patterns) for:
   - AWS access keys and secret keys
   - GCP credentials
   - GitHub tokens (classic and fine-grained)
   - GitLab tokens
   - OpenAI API keys
   - Anthropic API keys
   - Stripe keys
   - Private keys (RSA, SSH, PGP)
   - Generic Bearer tokens
   - Base64-encoded secrets
   - URLs with embedded credentials
   - Environment variable assignments

2. **Shannon Entropy Analysis**
   - Calculates entropy of strings to detect high-entropy (random) content
   - Flags strings above entropy threshold as likely passwords/API keys

3. **Allowlist**
   - Known false positive prefixes (e.g., "ghp_", "gho_", "github_pat_")

**Key Classes and Functions**:

```python
class Redactor:
    def redact_string(self, text: str) -> str:
        """Apply all redaction patterns to a string"""
        
    def redact_object(self, obj: Any) -> Any:
        """Recursively process dicts/lists"""
        
    @staticmethod
    def get_shannon_entropy(text: str) -> float:
        """Calculate Shannon entropy (0-8 bits)"""
```

### 5.4 anonymizer.py (106 lines)

Anonymizes usernames and file paths to protect privacy.

**Key Features**:

1. **Path Anonymization**
   - Strips home directory from paths
   - Example: `/Users/username/project/file.py` → `/home/user/project/file.py`

2. **Username Hashing**
   - SHA256 hashing with prefix "user_"
   - Consistent across sessions (same username → same hash)
   - Configurable extra usernames

3. **Project Name Normalization**
   - Removes path separators from project names

**Key Classes and Functions**:

```python
class Anonymizer:
    def __init__(self, extra_usernames: list[str] = None):
        self.extra_usernames = extra_usernames or []
        
    def anonymize_string(self, text: str) -> str:
        """Apply all anonymization transformations"""
        
    def anonymize_path(self, path: str) -> str:
        """Replace home directory references"""
        
    def hash_username(self, username: str) -> str:
        """SHA256 hash with 'user_' prefix"""
```

### 5.5 config.py (49 lines)

Persistent configuration management using JSON file storage.

**Config Location**: `~/.codercrucible/config.json`

**Settings**:

| Setting | Type | Description |
|---------|------|-------------|
| `repo` | str | Hugging Face repository (e.g., `username/my-data`) |
| `excluded_projects` | list[str] | Project directories to skip |
| `redact_strings` | list[str] | Custom strings to always redact |
| `redact_usernames` | list[str] | Additional usernames to anonymize |
| `stage` | int | Current workflow stage (1-4) |
| `projects_confirmed` | bool | Whether user confirmed project selection |
| `last_export` | dict | Metadata from last export |

---

## 6. Data Flow

### 6.1 Input

Claude Code session logs stored at:
```
~/.claude/projects/<project_name>/sessions/*.jsonl
```

Each `.jsonl` file contains one JSON object per line, representing a session.

### 6.2 Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Discover Projects                                       │
│ Scan ~/.claude/projects/ directories                            │
│ └─> Returns list of project directories                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Parse Sessions (parser.py)                              │
│ Read each .jsonl file                                           │
│ Extract: messages, tool calls, thinking, stats                  │
│ └─> Returns raw session data                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Anonymize (anonymizer.py)                                │
│ Replace /Users/username/ → /home/user/                          │
│ Hash usernames with SHA256                                       │
│ └─> Returns anonymized data                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Redact Secrets (secrets.py)                             │
│ Apply 20+ regex patterns                                        │
│ Entropy-based detection                                         │
│ Custom redact_strings                                           │
│ └─> Returns redacted data                                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Export (cli.py)                                         │
│ conversations.jsonl (one JSON per session)                      │
│ metadata.json (aggregate stats)                                  │
│ README.md (dataset card)                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Push to Hugging Face (optional)                         │
│ Upload via huggingface_hub                                       │
│ Private by default (or public if requested)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Privacy & Redaction (7 Layers)

CoderCrucible implements **7 protection mechanisms**:

1. **Path Anonymization** - Removes home directory paths
2. **Username Hashing** - SHA256 hashes usernames with prefix
3. **Regex Secret Detection** - 20+ patterns for API keys, tokens
4. **Entropy Detection** - Finds high-entropy strings (random passwords)
5. **Custom Redaction** - User-defined strings to redact
6. **Manual PII Audit** - User reviews before pushing (Stage 3)
7. **Private by Default** - Hugging Face datasets default to private

---

## 8. Output Data Schema

### 8.1 conversations.jsonl

One JSON object per session (newline-delimited JSON):

```json
{
  "session_id": "abc123",
  "project_name": "my-project",
  "messages": [
    {
      "type": "user",
      "content": "Hello, can you help me with this code?"
    },
    {
      "type": "assistant",
      "content": "Of course! I'll help you with that.",
      "thinking": "The user wants help with code. Let me read the file first.",
      "tool_calls": [
        {
          "name": "Read",
          "input": {"file_path": "src/main.py"},
          "output": "def main():\n    print('hello')"
        }
      ]
    }
  ],
  "token_counts": {
    "input": 1500,
    "output": 3000,
    "total": 4500
  },
  "duration_seconds": 3600.5,
  "message_count": 20,
  "tool_call_count": 5
}
```

### 8.2 metadata.json

Aggregate statistics from export:

```json
{
  "codercrucible_version": "0.2.1",
  "export_timestamp": "2024-01-15T12:00:00Z",
  "total_sessions": 50,
  "total_messages": 500,
  "total_tool_calls": 100,
  "total_tokens": 100000,
  "total_duration_seconds": 72000,
  "projects_included": ["project-a", "project-b"],
  "projects_excluded": ["private-project"]
}
```

### 8.3 README.md (Dataset Card)

Hugging Face dataset card with:
- Dataset description
- Usage examples
- Data schema
- Limitations and biases
- Citation information

---

## 9. Configuration Files

### 9.1 pyproject.toml

```toml
[project]
name = "codercrucible"
version = "0.2.1"
description = "Export Claude Code sessions to Hugging Face"
authors = [{name = "Author Name"}]
requires-python = ">=3.10"
dependencies = ["huggingface_hub>=0.20.0"]

[project.optional-dependencies]
dev = ["pytest"]

[project.scripts]
codercrucible = "codercrucible.cli:main"

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```

### 9.2 .github/workflows/test.yml

Tests on multiple Python versions:

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12', '3.13']
```

### 9.3 .github/workflows/publish.yml

PyPI trusted publishing workflow:
- Runs on push to main branch
- Requires tests to pass first
- No API tokens in repository (uses trusted publishing)

---

## 10. Testing

Test files in `tests/`:

| File | Coverage |
|------|----------|
| `conftest.py` | Pytest fixtures for shared test utilities |
| `test_cli.py` | CLI command tests |
| `test_config.py` | Configuration management tests |
| `test_parser.py` | Session parsing tests |
| `test_anonymizer.py` | Anonymization tests |
| `test_secrets.py` | Secret detection tests |

Run tests with:
```bash
pytest tests/
```

---

## 11. CI/CD Pipeline

### 11.1 Test Workflow (test.yml)

- **Triggers**: Every push and pull request
- **Python Versions**: 3.10, 3.11, 3.12, 3.13
- **Command**: `pytest tests/`

### 11.2 Publish Workflow (publish.yml)

- **Trigger**: Push to `main` branch
- **Steps**:
  1. Checkout code
  2. Set up Python
  3. Install dependencies
  4. Run tests
  5. Build package
  6. Publish to PyPI (trusted publishing)
- **Package**: https://pypi.org/project/codercrucible/

---

## 12. Documentation

### 12.1 README.md

Comprehensive documentation covering:
- Quick start guide
- Command reference table
- What data gets exported (messages, thinking, tool calls, tokens)
- Privacy & redaction layers explanation (7 mechanisms)
- Data schema for exported JSONL
- Instructions for finding datasets on Hugging Face

### 12.2 docs/SKILL.md

Claude Code agent skill definition:
- **Rule**: Always follow `next_steps` from JSON output
- **PII Audit Workflow** (6 steps):
  1. Run `codercrucible export`
  2. Review `redacted.jsonl` for sensitive data
  3. Check `secrets.log` for detected patterns
  4. Run `codercrucible config --add-redact-strings <strings>`
  5. Re-run `codercrucible export`
  6. Run `codercrucible confirm`
- Command reference
- Gotchas and warnings

---

## 13. Command Reference

| Command | Description |
|---------|-------------|
| `codercrucible` | Show help |
| `codercrucible prep` | Discover projects, check HF auth |
| `codercrucible status` | Show current stage and next steps |
| `codercrucible list` | List all projects with exclusion status |
| `codercrucible config` | View or set configuration |
| `codercrucible config --add-excluded <project>` | Exclude a project |
| `codercrucible config --add-redact-strings <strings>` | Add custom redaction |
| `codercrucible config --add-username <username>` | Add extra username to hash |
| `codercrucible export` | Export sessions to JSONL |
| `codercrucible export --push` | Export and push to Hugging Face |
| `codercrucible export --public` | Export as public dataset |
| `codercrucible confirm` | Confirm PII audit, enable pushing |
| `codercrucible update-skill` | Update Claude Code skill |

---

## 14. Hugging Face Integration

### 14.1 Authentication

Uses `huggingface_hub` for authentication:
- Checks for `HF_TOKEN` environment variable
- Falls back to `huggingface-cli login`
- Validates token before export

### 14.2 Repository Creation

- Creates repository if it doesn't exist
- Format: `username/dataset-name` (from config)
- Private by default

### 14.3 Upload

- Uses `create_repo` and `upload_folder` from `huggingface_hub`
- Files uploaded:
  - `conversations.jsonl`
  - `metadata.json`
  - `README.md`

---

## 15. Key Implementation Details

### 15.1 File Discovery

Claude Code stores sessions in:
```
~/.claude/projects/<project_name>/sessions/
```

Each project can have multiple session files (one per conversation).

### 15.2 Session File Format

Session files are JSONL (newline-delimited JSON) with:
- `sessionId` - Unique identifier
- `projectId` - Project reference
- `transcript` - List of message objects
- `summary` - Session statistics

### 15.3 Message Types

From session transcript:
- `input` - User messages
- `output` - Assistant responses
- May include `tool` - Tool invocations with input/output

### 15.4 Token Counting

Session metadata includes token counts from Claude Code's own tracking:
- `totalInputTokens`
- `totalOutputTokens`

---

## 16. Error Handling

The codebase includes error handling for:
- Missing Claude Code data directory
- Invalid JSON in session files
- Hugging Face authentication failures
- Network errors during upload
- Permission denied errors

---

## 17. Version Information

- **Current Version**: 0.2.1
- **Python Support**: 3.10, 3.11, 3.12, 3.13
- **License**: MIT

---

## 18. Summary

**CoderCrucible** is a privacy-focused CLI tool that:

1. **Discovers** Claude Code conversation history from `~/.claude/projects/`
2. **Parses** session JSONL files to extract messages, tool calls, and thinking
3. **Anonymizes** paths and usernames to protect privacy
4. **Redacts** secrets using 20+ regex patterns and entropy analysis
5. **Exports** structured JSONL datasets with metadata
6. **Uploads** to Hugging Face (private by default)
7. **Guides** users through a 4-stage workflow with confirmation prompts

The codebase demonstrates:
- Clean separation of concerns (CLI, parsing, anonymization, secrets, config)
- Comprehensive test coverage
- CI/CD with multiple Python versions
- Well-documented usage
- Privacy-first design with 7 layers of protection

The architecture prioritizes user privacy at every step while providing a seamless workflow for exporting conversation data to Hugging Face for AI training purposes.
