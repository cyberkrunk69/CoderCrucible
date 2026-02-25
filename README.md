# CoderCrucible

Turn your AI coding conversations into a clean, shareable, community‑owned dataset.

CoderCrucible is a privacy‑first tool that ingests logs from any coding assistant (Cursor, Copilot, Claude, Cline, Continue, etc.), strips away everything that could identify you or the provider, and outputs a unified, searchable, training‑ready dataset. You keep control. You choose what to share. Together, we build the world's largest open corpus of real human‑AI coding interactions.

📖 Read the Manifesto
Before you dive in, understand why this matters.
👉 [The CoderCrucible Manifesto – on data as power, waste as business model, and why your conversations belong to the world.](manifesto.txt)

Why CoderCrucible?
- Anonymization by default – Usernames, paths, model names, even invisible watermarks – all gone.
- Multi‑agent support – Works with Cursor, Copilot, Cline, Continue, Claude, Windsurf, and more.
- Local search – Instantly find past conversations with BM25F and AST‑based search.
- Optional enrichment – Add intent, emotion, and security tags using a small LLM (e.g., Groq 8B).
- Export to any format – JSONL, ChatML, Alpaca – ready for fine‑tuning or research.
- Auditable – Every change is logged so you know exactly what was redacted.

When you share your anonymized data, you're not just donating – you're breaking the data monopoly and forcing a race to the top: better models, lower prices, and real innovation. You're directly helping counter this sort of behavior: [Disputation on the power and efficacy of big AI](Disputation_on_the_power_and_efficacy_of_big_ai.md)


---

## Why this exists
Dataclaw was built to export Claude Code conversations to Hugging Face. While I believe that to be protected speech, I'm sure many disagree. This new project exists because Dataclaw (even the name is asking to be taken down) is too easily delegitimized and dismissed.
This is a good-faith effort to advance open source through voluntary, fully provider and user-PII anonymized data distribution. Huggingface has shown their true face already by taking down the personal logs of the author of Dataclaw from their servers. (404 free speech not found). So we go peer-to-peer or put it on the blockchain; I don't know, but I'm sure some of you have ideas..

- **Anonymization by default** – Not just usernames and paths, but also **model names**, provider fingerprints, and even subtle watermarks (like token‑specific patterns) are stripped.  
- **Local search** – Index your conversations with BM25F and AST, so you can instantly find that bug fix you discussed months ago.  
- **Semantic enrichment (optional)** – Use a small LLM (Groq 8B) to add intent, emotion, or security tags to your sessions – all running on your machine or with a cheap cloud call.  
- **Universal schema** – All conversations are normalized into a single format, ready for training, fine‑tuning, or research.  
- **Legally safer** – By removing provider‑specific signatures, watermarks, and invisible tokens, the resulting dataset becomes **unidentifiable** to its source. This protects you and respects the terms of service of the original AI providers.

Our goal is to **crowdsource a massive, high‑quality dataset of real coding conversations** – contributed voluntarily by users, fully anonymized, and clean of any proprietary fingerprints – to advance the next generation of coding models.

---

## Features

- **Multi‑agent support** – Parse conversations from:
  - Claude Code (original)
  - Cursor
  - GitHub Copilot Chat
  - Cline
  - Continue.dev
  - Windsurf / Codeium
  - (More coming soon)
- **Deep anonymization**:
  - Usernames and file paths → deterministic hashes
  - Model names → generic labels (`<model‑anthropic>`, `<model‑openai>`, etc.)
  - Provider‑specific phrasing and watermarks removed
  - Secret scanning (API keys, tokens, passwords) via regex + entropy
  - Email redaction
- **Local search**:
  - BM25F ranking with confidence scores
  - AST‑based fact extraction for code‑aware search
  - Fully offline, zero cost
- **Semantic enrichment (experimental)**:
  - `think-cheap` – Groq 8B adds intent, emotional tags, security markers (requires API key, but cheap)
  - `think-hard` – MiniMax for cross‑session pattern discovery (coming soon)
- **Export to universal training formats** – JSONL, ChatML, Alpaca, plain text
- **Privacy‑first** – All anonymization happens locally; nothing leaves your machine unless you explicitly choose to share.

---

## Quick Start

```bash
# Install
pip install codercrucible  # from this fork (once published) or from source

# Authenticate with Hugging Face (only if you want to upload)
huggingface-cli login --token YOUR_TOKEN

# Discover conversations from all supported agents
codercrucible discover

# Configure redaction (optional)
codercrucible config --redact-usernames "my_github_handle,my_discord_name"
codercrucible config --redact "my-domain.com,my-secret-project"

# Export locally, fully anonymized
codercrucible export --output ./my_data.jsonl

# Review and confirm (shows you what will be redacted)
codercrucible confirm

# Upload to Hugging Face (optional, always private by default)
codercrucible export --push
```

### Local search

```bash
# Build the search index (one-time)
codercrucible index

# Search your conversations
codercrucible search "authentication bug"
codercrucible search "API error" --limit 10
```

### Semantic enrichment (experimental)

```bash
# Enrich sessions with intent/emotion tags (requires Groq API key)
codercrucible think-cheap --dimensions intent,emotional
```

---

## How anonymization works

We apply multiple layers to ensure no traceable information remains:

| Layer | What it removes |
|-------|-----------------|
| Paths | `/Users/alice/project/file.py` → `~/project/file.py` |
| Usernames | `alice` → `user_a1b2c3d4` (deterministic hash) |
| Model names | `claude-3-5-sonnet-20241022` → `<model‑anthropic>` |
| Provider watermarks | Custom phrases like "As an AI from Anthropic" → generic |
| Secrets | API keys, JWTs, tokens → `<REDACTED>` |
| Emails | `alice@example.com` → `<email>` |
| Invisible tokens | Known token‑specific patterns (e.g., certain Unicode variations) stripped |

All replacements are logged to `~/.scout/audit.jsonl` so you can see exactly what was changed.

---

## The universal schema

Every conversation is normalized into a single JSONL format, making it easy to combine datasets from different sources and use them for training.

```json
{
  "meta": {
    "source_agent": "cursor",
    "session_id": "uuid-v4",
    "project_hash": "sha256-of-project-root",
    "start_time": 1729900000,
    "end_time": 1729903600,
    "quality_score": 0.85,
    "schema_version": "1.0"
  },
  "messages": [
    {
      "index": 0,
      "role": "user",
      "content": "Refactor the login function to use OAuth.",
      "timestamp": 1729900000,
      "annotations": {
        "file_refs": ["src/auth/login.ts"],
        "tool_calls": null
      }
    },
    {
      "index": 1,
      "role": "assistant",
      "content": "Here is the refactored code...",
      "timestamp": 1729900050,
      "annotations": {
        "file_refs": ["src/auth/login.ts"],
        "tool_calls": [
          {
            "name": "write_to_file",
            "args": { "path": "src/auth/login.ts", "content": "..." },
            "result": "success"
          }
        ],
        "thinking": "I need to ensure backward compatibility..."
      }
    }
  ]
}
```

---

## Why this is legally safer

AI providers often embed subtle fingerprints in their outputs – model names, specific phrasing patterns, or even invisible Unicode characters. By aggressively stripping these, we produce a dataset that **cannot be easily traced back to a specific provider**. This:

- Protects you from potential terms‑of‑service disputes.
- Enables truly open research without fear of retraction.
- Allows the community to build on data from many sources without contamination.

Of course, **no method is perfect**. We encourage you to review your data before sharing. The tool always exports locally first, and you must explicitly run `codercrucible confirm` to see what will be redacted before any upload.

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Our immediate roadmap:

- [ ] Add support for more agents (Tabnine, Codeium, etc.)
- [ ] Improve watermark detection (ML‑based fingerprint removal)
- [ ] Add quality scoring (heuristic + LLM)
- [ ] Build a public dataset repository on Hugging Face with a unified license

---

## License

This fork is released under the **MIT License**, same as the original CoderCrucible. All contributed data remains the property of the contributors; we only provide the tool.

---

## Acknowledgments

Huge thanks to the original CoderCrucible authors for the excellent foundation. This fork builds on their work to create a more privacy‑conscious, legally‑safe, and feature‑rich tool for the community.
