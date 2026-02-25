# CoderCrucible Research Report

**Date:** February 25, 2026  
**Repository:** https://github.com/cyberkrunk69/CoderCrucible  
**Local Path:** `/Users/vivariumenv1/GITHUBS/codercrucible`

---

## Executive Summary

CoderCrucible is a privacy-first tool for anonymizing and exporting AI coding assistant conversations. After rebranding from `dataclaw`, the codebase is in a **functional but incomplete state** with significant work needed on multi-agent parser support, CLI integration, and the enrichment pipeline.

### Key Findings

| Area | Status | Notes |
|------|--------|-------|
| Parser | ⚠️ Partial | Only Claude Code parser fully implemented; others are stubs |
| CLI | ✅ Functional | Complete with search, config, export, status commands |
| Anonymization | ✅ Functional | Uses `scout.tools.AnonymizerTool`; model name anonymization untested |
| Search | ✅ Functional | BM25-based with `scout.search.SearchIndex` |
| Enrichment | 🔶 Stub | Class structure exists but no CLI integration |
| Tests | ✅ Good | 1,915 lines across 6 test files |
| Config | ✅ Functional | JSON-based at `~/.codercrucible/config.json` |

### Critical Gaps

1. **Multi-agent support is not implemented** – The README claims support for Cursor, Copilot, Cline, Continue, Windsurf, but only Claude Code parsing exists
2. **Model name anonymization** – Uses scout-core's `AnonymizerTool` but no explicit model name replacement
3. **Enrichment CLI** – The `think-cheap` command is not wired into `cli.py`
4. **Package name mismatch** – Internal package is still `dataclaw` (folder: `codercrucible/dataclaw/`)

---

## Detailed Inventory

### Source Modules

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `dataclaw/__init__.py` | 4 | Version info | ✅ |
| `dataclaw/cli.py` | 1,062 | CLI entry point | ✅ Functional |
| `dataclaw/parser.py` | 391 | Claude Code parser | ⚠️ Claude only |
| `dataclaw/search.py` | 311 | BM25 search | ✅ Functional |
| `dataclaw/config.py` | 50 | Config management | ✅ Functional |
| `dataclaw/secrets.py` | 249 | Secret detection/redaction | ✅ Functional |
| `dataclaw/enrichment.py` | 368 | Semantic enrichment | 🔶 Stub (no CLI) |

### Test Files

| File | Lines | Coverage |
|------|-------|----------|
| `tests/conftest.py` | 63 | Fixtures |
| `tests/test_parser.py` | 440 | Parser logic |
| `tests/test_cli.py` | 365 | CLI commands |
| `tests/test_secrets.py` | 431 | Secret detection |
| `tests/test_anonymizer.py` | 222 | Anonymization |
| `tests/test_enrichment.py` | 323 | Enrichment logic |

### Configuration

- **Location:** `~/.codercrucible/config.json`
- **Defaults:** `dataclaw/config.py` lines 25-29

```python
DEFAULT_CONFIG = {
    "repo": None,
    "excluded_projects": [],
    "redact_strings": [],
}
```

### Dependencies

From `pyproject.toml`:

```toml
dependencies = [
    "huggingface_hub>=0.20.0",
    "scout-core @ git+https://github.com/cyberkrunk69/Scout.git@main",
]
```

**Scout-Core Imports:**

| Module | Used In | Purpose |
|--------|---------|---------|
| `scout.tools.AnonymizerTool` | `parser.py`, `search.py` | Path/text anonymization |
| `scout.search.SearchIndex` | `search.py` | BM25 indexing |
| `scout.audit.get_audit` | `enrichment.py` | Cost logging (optional) |

---

## Gap Analysis

### 1. Parser Infrastructure ❌

**Current State:**
- Only Claude Code parser is implemented
- No registry or plugin system for additional agents

**What Claims to Exist (README):**
- Cursor
- GitHub Copilot Chat
- Cline
- Continue.dev
- Windsurf / Codeium

**Reality:**
- None of these parsers exist in `parser.py`
- No `ParserRegistry` class
- No discover/parse functions for other agents

**Required Work:**
- [ ] Create parser registry pattern
- [ ] Implement Cursor parser
- [ ] Implement Copilot parser
- [ ] Implement Cline parser
- [ ] Implement Continue parser
- [ ] Implement Windsurf parser

### 2. Model Name Anonymization ⚠️

**Current State:**
- Uses `scout.tools.AnonymizerTool`
- No explicit model name replacement in code
- Claims to replace `claude-3-5-sonnet-20241022` → `<model-anthropic>`

**Required Work:**
- [ ] Verify model name anonymization works
- [ ] Add explicit model name replacement to parser
- [ ] Test with real Claude Code exports

### 3. CLI Integration ⚠️

**Current Commands:**
```
codercrucible prep          # Data prep - discover projects
codercrucible status        # Show stage and next steps
codercrucible confirm       # Scan for PII, unlock pushing
codercrucible list          # List all projects
codercrucible config        # View/set config
codercrucible export        # Export and push to HF
codercrucible index         # Build search index
codercrucible search        # Search indexed sessions
codercrucible update-skill  # Install skill for agent
```

**Missing Commands:**
- [ ] `think-cheap` - Not wired into CLI
- [ ] `think-hard` - Not implemented
- [ ] `discover` - Mentioned in README but not in CLI

### 4. Enrichment Module ⚠️

**Current State:**
- `EnrichmentOrchestrator` class exists
- Supports dimensions: `emotional`, `security`, `intent`
- Uses async/await pattern
- Integrates with `scout.audit` for cost logging
- **Not connected to CLI**

**Required Work:**
- [ ] Wire `think-cheap` into CLI
- [ ] Add Groq API key configuration
- [ ] Test batch processing
- [ ] Implement `think-hard` for cross-session patterns

### 5. Search Module ✅

**Current State:**
- Uses `scout.search.SearchIndex`
- BM25-based ranking
- Indexes RAW content (un-anonymized) for searchability
- Anonymizes at display time
- Configurable max content length

**Tested:** Yes, has test coverage

### 6. Secrets/Redaction ✅

**Current State:**
- 25+ secret patterns (JWT, API keys, tokens, emails, IPs)
- Allowlist for false positives
- Shannon entropy detection for unknown secrets
- Custom string redaction

**Tested:** Yes, 431 lines of tests

### 7. Package Naming 🔶

**Issue:**
- Folder: `/codercrucible/` (correct)
- Package: `dataclaw/` (should be `codercrucible/`)
- Import: `from dataclaw import ...` (should be `from codercrucible import ...`)

**Required Work:**
- [ ] Rename `dataclaw/` folder to `codercrucible/`
- [ ] Update all imports in source and tests
- [ ] Update `pyproject.toml` entry points

### 8. pyproject.toml Updates Needed

```toml
# Current (outdated)
name = "codercrucible"
description = "Export your Claude Code conversations to Hugging Face as structured training data"

# Should be
name = "codercrucible"
description = "Privacy-first tool to anonymize AI coding conversations into community-owned datasets"
```

---

## Reuse Opportunities

### From Scout-Core

| Component | Status | Reuse |
|-----------|--------|-------|
| `AnonymizerTool` | ✅ In Use | Paths, usernames, text |
| `SearchIndex` | ✅ In Use | BM25 search |
| `ScoutConfig` | ⚠️ Not Used | Could use for unified config |
| `scout.audit` | ⚠️ Optional | Cost logging in enrichment |

### Potential Improvements

1. **Unified Config** – Use `scout.config.ScoutConfig` instead of custom JSON config
2. **Shared Audit** – Full integration with `scout.audit` for all operations
3. **LLM Router** – Use `scout.llm.router` for enrichment calls instead of custom implementation

---

## Updated Roadmap

### Phase 1: Foundation (High Priority)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Rename package `dataclaw` → `codercrucible` | 1 day | None |
| Fix pyproject.toml URLs | 1 hour | None |
| Verify model name anonymization | 2 hours | Claude Code exports |
| Add `discover` CLI command | 1 day | Parser registry |

### Phase 2: Multi-Agent Parsers (High Priority)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Create parser registry pattern | 2 days | None |
| Implement Cursor parser | 2 days | Registry |
| Implement Copilot parser | 2 days | Registry |
| Implement Cline parser | 2 days | Registry |
| Implement Continue parser | 2 days | Registry |
| Implement Windsurf parser | 2 days | Registry |

### Phase 3: Enrichment (Medium Priority)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Wire `think-cheap` into CLI | 1 day | None |
| Add Groq API key config | 2 hours | Config system |
| Test batch enrichment | 1 day | Groq API key |
| Implement `think-hard` | 3 days | think-cheap |

### Phase 4: Polish (Low Priority)

| Task | Effort | Dependencies |
|------|--------|--------------|
| Add CONTRIBUTING.md | 2 hours | None |
| Update README with真实stats | 1 hour | None |
| Add more secret patterns | Ongoing | User reports |
| Performance optimization | 1 week | Profiling |

---

## Actionable Next Steps

### Immediate (Today)

1. **Rename package folder** from `dataclaw/` to `codercrucible/` and update all imports
2. **Fix pyproject.toml** URLs to point to new repo
3. **Verify existing Claude Code parser** works with test data

### This Week

4. **Create parser registry** – Design and implement plugin pattern
5. **Implement Cursor parser** – Highest demand, most similar to Claude Code
6. **Wire enrichment CLI** – Connect `think-cheap` to main CLI

### This Month

7. **Implement remaining parsers** – Copilot, Cline, Continue, Windsurf
8. **Add comprehensive tests** for all parsers
9. **Document contribution guidelines** – CONTRIBUTING.md

---

## Appendix: File Locations

```
codercrucible/
├── .claude/skills/dataclaw/SKILL.md
├── .github/workflows/
│   ├── test.yml
│   └── publish.yml
├── dataclaw/                    # ⚠️ Should be codercrucible/
│   ├── __init__.py
│   ├── cli.py                   # 1,062 lines
│   ├── config.py                # 50 lines
│   ├── enrichment.py            # 368 lines
│   ├── parser.py                # 391 lines
│   ├── search.py                # 311 lines
│   └── secrets.py               # 249 lines
├── docs/SKILL.md
├── tests/
│   ├── conftest.py              # 63 lines
│   ├── test_anonymizer.py       # 222 lines
│   ├── test_cli.py              # 365 lines
│   ├── test_config.py           # 71 lines
│   ├── test_enrichment.py       # 323 lines
│   ├── test_parser.py           # 440 lines
│   └── test_secrets.py          # 431 lines
├── CODEBASE_REPORT.md
├── INTEGRATION_REPORT.md
├── REFACTOR_REPORT.md
├── REPORT_Search_Anonymization_Fix.md
├── README.md
├── manifesto.txt
├── pyproject.toml
└── LICENSE
```

---

*Report generated: February 25, 2026*
