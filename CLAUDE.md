# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Observatório de Manaus** is an automated news monitoring platform for Manaus and Amazonas. It collects articles from 40+ RSS feeds (news portals, blogs, YouTube channels, government agencies), classifies them by topic and locality, and displays them in a Streamlit dashboard. Daily email digests are sent to subscribers.

The system runs on **Railway** with two services:
- **Web**: Streamlit dashboard
- **Worker**: Collector + NLP pipeline (runs every 30 minutes)

## Architecture

```
RSS/YouTube Sources (40+ feeds)
        ↓ (collect every 30 min)
Coletor (rss_collector.py + youtube_collector.py)
        ↓
MySQL Database (Railway)
        ↓
NLP Pipeline (runs in same cycle)
  ├─ classifier.py       → topic classification (regex + keywords)
  ├─ local_classifier.py → is_local classification (700+ keywords + Groq fallback)
  ├─ summarizer.py       → daily summaries (Groq LLM)
  └─ backfill_transcripts.py → YouTube video transcription (Groq Whisper)
        ↓
Streamlit Dashboard (display + filtering)
        ↓
Email Digest (daily at 7am Manaus time, via Sendgrid or Brevo)
```

**Data flow:**
1. **Collection cycle** (`runner.py` → `job()` every 30 min):
   - `run_collection()` — fetch RSS feeds
   - `run_youtube_collection()` — fetch YouTube videos + transcripts
   - `run_classification()` — classify articles by topic (pre-computed regex keywords)
   - `run_local_classification()` — determine if article is about Manaus/AM (700+ keywords + Groq for edge cases)
   - `backfill()` — process up to 10 pending video transcriptions
   - `run_daily_summary()` + `run_topic_summaries()` — generate AI summaries (Groq)
   - `run_digest()` — send daily email if summaries exist

2. **Dashboard** (`dashboard/0_Visão_Geral.py` + pages):
   - Query articles by topic, source, date, keyword
   - **Default: show only `is_local=True`** articles (with toggle to include all)
   - Display metrics, charts, word cloud, daily summary

## Quick Start

### Local Setup

```bash
cd /home/tiago/obs-manaus

# Create .env file (copy from .env.example)
cp .env.example .env
# Edit .env with your credentials:
#   - MYSQL_HOST/PORT/USER/PASSWORD/DATABASE
#   - GROQ_API_KEY (for Groq Llama + Whisper)
#   - SENDGRID_API_KEY or BREVO_API_KEY (for email digest)
#   - ADMIN_PASSWORD (for dashboard admin panel)

# Install Python 3.11 + dependencies
pip install -r requirements.txt

# Ensure ffmpeg is installed (needed for video processing)
# On macOS: brew install ffmpeg
# On Linux: sudo apt install ffmpeg
# On Windows: choco install ffmpeg
```

### Running Locally

**Collector (every 30 min):**
```bash
python collector/runner.py
```
Bootstraps DB schema, seeds topics/sources, then runs collection job immediately and every 30 min thereafter. Logs to stdout.

**Dashboard:**
```bash
streamlit run "dashboard/0_Visão_Geral.py"
```
Opens at http://localhost:8501. Uses `.streamlit/config.toml` for theme/layout settings.

**Test email digest locally:**
```bash
python scripts/test_digest.py
```

### Database

MySQL with SQLAlchemy 2.0 ORM. Schema auto-migrates on startup (`db/connection.py`).

**Key models** (`db/models.py`):
- `Source` — news portals, blogs, YouTube channels, gov agencies
- `Topic` — 12 predefined topics + "Outros" (each with keywords, color, display order)
- `Article` — news items + videos (with `is_local` boolean + `topic_id`)
- `DailySummary` — AI-generated summaries (general + per-topic)
- `EmailSubscription` + `DigestLog` — email subscribers + send history

All timestamps stored in UTC; dashboard converts to Manaus time (UTC−4).

## Key Modules

### Collection (`collector/`)
- **`rss_collector.py`** — uses `feedparser` to fetch RSS feeds, deduplicate by URL, store articles
- **`youtube_collector.py`** — fetches YouTube feed RSS, attempts YouTube auto-captions first, falls back to Groq Whisper (`whisper-large-v3`)
- **`runner.py`** — orchestrates the 30-min cycle: collection → classification → summarization → digest

### NLP (`nlp/`)
- **`classifier.py`** — regex-based topic classification using word-boundary matching on keywords from `topics` table. Falls back to "Outros" if no match
- **`local_classifier.py`** — hybrid: first tries 700+ hardcoded local keywords (loaded from `nlp/local_keywords.json`), then uses Groq LLM if ambiguous
- **`summarizer.py`** — generates daily + topic-specific AI summaries using Groq `llama-3.1-8b-instant`. Stores in `daily_summaries` table

### Dashboard (`dashboard/`)
- **`0_Visão_Geral.py`** — main page (metrics, volume chart, top sources/topics, word cloud, daily summary card)
- **`pages/1_Temas.py`** — topic detail + topic-specific summaries
- **`pages/2_Sobre.py`** — institution info, source list, email signup form
- **`components/summary_card.py`** — reusable UI card for AI-generated summaries

### Email Digest (`notifications/email_sender.py`)
- **Strategy:** Sendgrid API (preferred for Railway) with Brevo REST API as fallback
- **Trigger:** runs at end of collection cycle; only sends if daily summaries exist
- **Schedule:** hardcoded 7:00 AM Manaus time via `apscheduler` (in Railway Worker service)
- **Content:** general + topic-specific summaries, article counts, unsubscribe link
- **Logging:** `DigestLog` table tracks sent date + recipient count

## Important Notes

### Email / Digest System

**Recent refactor (May 2026):** Switched from SMTP (Brevo/Sendgrid) to REST APIs for better reliability on Railway.

**Config:**
- `.env` should have **either** `SENDGRID_API_KEY` **or** `BREVO_API_KEY` (Sendgrid preferred)
- `ADMIN_PASSWORD` required for `/admin` panel (test digest button)
- On Railway, set these as **service variables** (not secrets, so collector + web both see them)

**Troubleshooting:** See `BREVO_TROUBLESHOOTING.md` + `SENDGRID_SETUP.md` if digest fails

### Timestamps

- All DB timestamps stored in **UTC** (`datetime.utcnow()`)
- Manaus time is **UTC−4, no DST** — converted at display time in dashboard
- Daily summaries keyed by Manaus date (not UTC date)

### Classification

- **Topic:** regex keywords from `topics` table (fast, deterministic)
- **Is_local:** 700+ hardcoded keywords first (fast), Groq LLM for edge cases (slower)
- Both run in collection cycle; retry logic in place for transient Groq timeouts

## Deployment (Railway)

Two services in one Railway project:

1. **Web** (Procfile):
   ```bash
   streamlit run "dashboard/0_Visão_Geral.py"
   ```

2. **Worker**:
   ```bash
   python collector/runner.py
   ```

Both need same env vars: `DATABASE_URL`, `GROQ_API_KEY`, `SENDGRID_API_KEY` (or `BREVO_API_KEY`), `ADMIN_PASSWORD`.

Deploy on push to `main` branch (GitHub integration).

## Recent Changes

- **May 2026:** Email digest refactored to use REST APIs (Sendgrid primary, Brevo fallback) instead of SMTP for better Railway reliability
- **May 2026:** Documentation added (`SENDGRID_SETUP.md`, `BREVO_TROUBLESHOOTING.md`, `DEPLOYMENT.md`)

## Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.11 |
| Dashboard UI | Streamlit 1.35 |
| Database | MySQL 8 (Railway) |
| ORM | SQLAlchemy 2.0 |
| Scraping | feedparser, beautifulsoup4, yt-dlp |
| NLP / Summarization | Groq (llama-3.1-8b-instant, whisper-large-v3) |
| Charting | Plotly, matplotlib (word cloud) |
| Email | Sendgrid or Brevo REST APIs |
| Scheduling | schedule (collection), apscheduler (digest) |
| Hosting | Railway (MySQL + Python app) |
