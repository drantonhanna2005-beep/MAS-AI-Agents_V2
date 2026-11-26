# 🧠 MAS AI Agents — Intelligent Academic Multi-Agent System & Multimodal AI Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/drantonhanna2005-beep/MAS-AI-Agents)

**MAS AI Agents** (Multi-Agent System Academic Hub) is an autonomous, multimodal multi-agent artificial intelligence platform designed to deliver personalized academic advisory, study planning, deterministic GPA computations, career guidance (ATS resume generation), document-grounded Retrieval-Augmented Generation (RAG), and real-time voice interaction.

Built upon clean architectural patterns from [awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps), MAS AI Agents operates with **zero mandatory paid dependencies** — providing full local execution via Ollama and offline fallback modes, alongside seamless cloud provider acceleration (Groq, OpenRouter, Google Gemini).

---

## 📑 Table of Contents

- [1. Overview](#1-overview)
- [2. Main Features](#2-main-features)
- [3. Technology Stack](#3-technology-stack)
- [4. Project Architecture](#4-project-architecture)
- [5. Installation Requirements](#5-installation-requirements)
- [6. Environment Variable Configuration](#6-environment-variable-configuration)
- [7. Database Setup](#7-database-setup)
- [8. Installation Instructions](#8-installation-instructions)
- [9. Application Startup Commands](#9-application-startup-commands)
- [10. AI Provider Configuration](#10-ai-provider-configuration)
- [11. API and Integration Overview](#11-api-and-integration-overview)
- [12. Security and Privacy Notes](#12-security-and-privacy-notes)

---

## 1. Overview

**MAS AI Agents** unites a team of 9 specialized AI agents coordinated by an intelligent dynamic router. The platform provides a modern, interactive web chat interface featuring real-time Server-Sent Events (SSE) streaming, bilingual interface support (Arabic RTL and English LTR), deep-thinking chain visualization, and source attribution.

Whether deployed locally on a student workstation or hosted in an academic department, MAS ensures privacy, deterministic calculation accuracy, and zero vendor lock-in.

---

## 2. Main Features

- 🧭 **Intelligent Multi-Agent Orchestration**: Automatic intent classification and deterministic triage dispatching queries to one or more collaborating agents.
- 🤖 **9 Specialized Domain Agents**:
  1. **Academic Advisor**: Degree paths, course prerequisites, credit hours, department selection (AI, Cybersecurity, Bioinformatics).
  2. **Study Planner**: Weekly study schedules, exam prep timelines, milestone tracking.
  3. **GPA Calculator**: Deterministic, 100% accurate GPA calculation (4.0 and 5.0 scales, cumulative tracking).
  4. **Financial Affairs Agent**: University tuition structures, payment channels (InstaPay, Banque Misr, QNB, e-wallets).
  5. **Campus Life Agent**: Student platforms, IDs, military education requirements, student union services.
  6. **Housing & Local Services Agent**: Student housing directories, clinics, pharmacies, transportation routes.
  7. **Career & ATS Resume Agent**: Automated ATS-compliant CV audit, score analysis, keyword matching, and editable DOCX/PDF export.
  8. **Learning Resources Agent**: Curated recommendations across ITI, NTI, Coursera, Google, YouTube, and Cisco.
  9. **General Research & Vision Agent**: Internet search synthesis, document parsing, and multimodal image inspection.
- ⚡ **Hybrid RAG Knowledge Engine**:
  - Combined BM25 lexical search and semantic dense vector embeddings.
  - Multi-format ingestion: PDF, DOCX, XLSX, PPTX, CSV, TXT, and images.
  - Transparent citation with source excerpt cards.
- 🎙️ **Multimodal Voice & Vision Interaction**:
  - Speech-to-Text (STT) via Whisper-large-v3-turbo and Gemini audio transcription.
  - Natural Text-to-Speech (TTS) integration.
  - Image analysis for visual reasoning (charts, schedules, exam sheets).
- 🌐 **Instant Bilingual Support**: Real-time Arabic (RTL) and English (LTR) localization with one-click full interface and message translation.
- 🛡️ **Autonomous Provider Fallback Chain**: Graceful, uninterrupted failover across OpenRouter → Google Gemini → Groq → Local Ollama → Offline RAG mode.

---

## 3. Technology Stack

- **Backend Framework**: Python 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **Frontend Architecture**: Vanilla ES6+ JavaScript, CSS3 (Modern Glassmorphism & Adaptive Dark/Light Mode), HTML5
- **Data Persistence**: SQLite (WAL Mode, Thread-Safe Connection Locking)
- **Document Processing**: `pypdf`, `python-docx`, `openpyxl`, `python-pptx`
- **Retrieval & RAG**: BM25 lexical ranking + Hybrid Dense Vector Search
- **AI Integrations**:
  - [Ollama](https://ollama.com/) (Local, fully private, no internet required)
  - [OpenRouter](https://openrouter.ai/) (Free tier models: Gemma, Nemotron, Llama)
  - [Google Gemini API](https://aistudio.google.com/) (Multimodal vision & audio)
  - [Groq Cloud](https://groq.com/) (Ultra-low latency inference & Whisper STT)

---

## 4. Project Architecture

```
MAS-AI-Agents/
├── app.py                   # FastAPI server entry point, REST endpoints, SSE streaming
├── ingest.py                # Document parser, chunker, and vector index builder
├── config.example.json      # Configuration template with safe placeholder values
├── .env.example             # Environment variables template
├── requirements.txt         # Core dependencies
├── run.bat                  # One-click Windows launch script
├── train_data.bat           # Ingestion batch script
├── agents/                  # Multi-agent domain logic
│   ├── orchestrator.py      # Router, multi-agent collaboration, streaming pipeline
│   ├── registry.py          # Agent system prompts, tool bindings, domain definitions
│   └── __init__.py
├── core/                    # Underlying engine modules
│   ├── config.py            # Dynamic configuration manager & validation
│   ├── llm.py               # Unified streaming client (Ollama/Groq/OpenRouter/Gemini)
│   ├── rag.py               # Hybrid BM25 + dense embedding vector search
│   ├── knowledge.py         # Static academic knowledge base & quick links
│   ├── history.py           # Thread-safe SQLite conversation history storage
│   ├── gpatool.py           # Deterministic GPA & grading calculation engine
│   ├── cvgen.py             # ATS CV evaluation & Word/HTML generation
│   ├── extract.py           # Multimodal document text extraction
│   ├── websearch.py         # Free DuckDuckGo internet search integration
│   ├── translate.py         # Hybrid LLM & neural translation pipeline
│   └── __init__.py
├── web/                     # Web application frontend assets
│   ├── index.html           # Main chat & multi-agent workspace UI
│   ├── share.html           # Shared conversation viewer
│   ├── style.css            # Responsive, dark/light theme stylesheet
│   ├── app.js               # Reactive chat client, SSE handler, audio recorder
│   ├── i18n.js              # Bilingual Arabic/English dictionary
│   ├── share.js             # Share link viewer logic
│   └── assets/              # Icons, logos, and favicon
├── data/                    # Academic knowledge source directories (RAG source)
├── index_store/             # Precomputed search indexes and metadata
└── uploads/                 # Temporary user session uploads (excluded from git)
```

---

## 5. Installation Requirements

- **Operating System**: Windows 10/11, Ubuntu 20.04+, or macOS 12+
- **Python**: Version 3.10 or higher
- **Hardware Requirements**:
  - *Cloud Mode*: Any standard dual-core PC with 4GB RAM.
  - *Local Mode (Ollama)*: 8GB+ RAM (16GB recommended for 8B models), optional GPU.

---

## 6. Environment Variable Configuration

Create a `.env` file in the root directory or copy `.env.example`:

```bash
cp .env.example .env
```

Configure your parameters:

```ini
# Provider API Keys (Optional - leaving empty defaults to Local/Offline mode)
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Local LLM Endpoint
OLLAMA_URL=http://localhost:11434

# Server Configuration
APP_HOST=0.0.0.0
APP_PORT=8765
```

Alternatively, settings can be managed directly at runtime via `config.json` or the **⚙️ Settings** modal in the web interface.

---

## 7. Database Setup

MAS AI Agents utilizes an embedded, zero-configuration SQLite database (`history.db`) for chat storage.

- **Initialization**: Automatically initialized upon first startup via `core/history.py`.
- **Concurrency**: Configured with `WAL` (Write-Ahead Logging) and thread-safe mutex locks for concurrent read/write protection.
- **Privacy**: The database file is local to the deployment host and ignored in Git to prevent data leakage.

---

## 8. Installation Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/drantonhanna2005-beep/MAS-AI-Agents.git
   cd MAS-AI-Agents
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize configuration**:
   ```bash
   # Copy configuration template
   cp config.example.json config.json
   ```

---

## 9. Application Startup Commands

### Quick Start (Windows)
Double-click `run.bat` or run:
```bat
run.bat
```

### Manual CLI Start (Cross-Platform)
```bash
python app.py
```
By default, the server listens at `http://localhost:8765`. If port 8765 is occupied, it automatically increments to the next available port.

To specify a custom port:
```bash
python app.py --port 9000 --host 127.0.0.1
```

---

## 10. AI Provider Configuration

MAS AI Agents supports 4 execution modes configured under `config.json` or in the web UI:

| Provider | Cost | Setup | Supported Capabilities |
|---|---|---|---|
| **Ollama** | 100% Free / Offline | Install from [ollama.com](https://ollama.com) & run `ollama pull llama3.1:8b` | Chat, RAG, Reasoning |
| **OpenRouter** | Free Tier Available | API key from [openrouter.ai](https://openrouter.ai) | Chat, Embeddings, Voice (HeyGen/Fish) |
| **Google Gemini** | Free Tier Available | API key from [aistudio.google.com](https://aistudio.google.com) | Multimodal Vision, Audio Transcription, Chat |
| **Groq Cloud** | Free Tier Available | API key from [console.groq.com](https://console.groq.com) | Ultra-fast inference, Whisper STT |

---

## 11. API and Integration Overview

The FastAPI backend provides structured REST endpoints and an SSE stream:

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat/stream` | `POST` | Real-time Server-Sent Events (SSE) chat and multi-agent streaming |
| `/api/chats` | `GET` / `POST` | List conversations or create a new session |
| `/api/chats/{chat_id}` | `GET` / `DELETE` | Retrieve conversation history or delete a session |
| `/api/agents` | `GET` | List available agents, personas, and capabilities |
| `/api/settings` | `GET` / `POST` | Read or update runtime configuration and model keys |
| `/api/upload` | `POST` | Upload and extract content from PDF, Word, Excel, and images |
| `/api/gpa` | `POST` | Execute deterministic GPA calculations |
| `/api/cv/analyze` | `POST` | Evaluate CV text against ATS criteria |
| `/api/cv/generate` | `POST` | Generate formatted HTML / DOCX resume files |
| `/api/stt` | `POST` | Audio file speech-to-text transcription |
| `/api/translate` | `POST` | Multi-engine text translation |

---

## 12. Security and Privacy Notes

- **Zero Secret Leakage**: No API keys, passwords, or credentials are hardcoded or tracked in repository history. All secret keys remain local in `config.json` or `.env`.
- **Local Data Isolation**: Chat sessions (`history.db`), indexed embeddings (`index_store/`), and user file uploads (`uploads/`) are excluded from Git version control.
- **Strict File Upload Validation**: Uploaded files undergo extension validation, sanitized naming, and sandboxed storage in `uploads/`.
- **XSS & DOM Sanitization**: Frontend outputs are escaped and rendered through safe HTML parsers.
- **Audit Compliance**: Designed to comply with academic privacy guidelines; conversations are stored exclusively on the user's host machine.


---

## 13. Providers, CI and Safe Publishing

### Anthropic (Claude) provider
Claude is supported as a first-class provider alongside Groq, OpenRouter, Gemini and Ollama.
It can be configured two ways:

- **UI**: Settings → Provider → `Anthropic Claude`, then paste the key and choose a model.
- **Environment (recommended for deployment)**: `ANTHROPIC_API_KEY` (and optional `ANTHROPIC_BASE_URL`
  for an OpenAI-compatible gateway). Environment variables override `config.json`, so no key is
  ever committed to Git.

Vision (images) is supported for all Claude models. Audio and video are handled by the existing
speech-to-text (Whisper/Gemini) and frame-extraction pipelines — Claude does not accept raw audio/video.

### Continuous integration
`.github/workflows/ci.yml` runs on every push to `main`: Python/JS syntax checks, a backend import +
database smoke test, the network-free unit tests (GPA, regressions, fallback) and a credential scan.

### Publishing workflow
See [PUBLISHING.md](PUBLISHING.md). A ready-made script performs preflight checks, runs the tests,
scans for secrets, merges the remote safely (never force-pushes) and verifies that the remote SHA
matches the local one:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish.ps1 -Message "feat: my change"
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
