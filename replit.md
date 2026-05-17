# ShareChat Trending Tags System

A FastAPI backend for an APM assignment that identifies what is trending in India today for Hindi-speaking ShareChat users, returning a ranked list of 10 trending tags per invocation.

## Run & Operate

- `cd sharechat-api && uvicorn main:app --host 0.0.0.0 --port 8000` — run the API server
- Workflow: **ShareChat Trends API** — auto-managed, runs on port 8000

## Stack

- Python 3.11 + FastAPI + Uvicorn
- feedparser — Google News & Reddit RSS parsing
- pytrends — Google Trends India (with graceful fallback)
- In-memory processing only — no DB, no cache, no auth

## Where things live

- `sharechat-api/main.py` — entire backend: pipeline, scoring, endpoints
- `sharechat-api/requirements.txt` — Python dependencies
- `sharechat-api/README.md` — data sources, pipeline, scoring formula, limitations, roadmap

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/trends` | Top 10 trending tags (JSON) |
| `GET` | `/debug/trends` | HTML table for demos & Loom walkthroughs |

## Architecture decisions

- **Keyword map drives everything** — `KEYWORD_TO_TAG` maps English keywords → Hindi hashtag + category. Simple, explainable to a non-engineer PM audience.
- **Three signal sources** — Google News RSS (news), pytrends (search), Reddit RSS (social) weighted 40/30/20. Recency adds up to 10 for freshness.
- **Graceful degradation** — each source catches its own exceptions. API returns valid results even if pytrends is blocked or Reddit is rate-limited.
- **Fallback padding** — if live sources return < 10 topics, `FALLBACK_TOPICS` fills the gap, clearly marked as `"Google News (fallback)"` in `sources[]`.
- **Fresh on every call** — no build-time caching. Every `/api/trends` call re-fetches all sources.

## Product

Returns 10 trending tags for Hindi-speaking Indian ShareChat users, each with: rank, Hindi hashtag, category (Hindi + English key), heat score (0–100), momentum label (Breaking/Rising/New), signal breakdown, sources, and a human-readable `whyTrending` explanation.

## User preferences

- Keep implementation lightweight and prototype-friendly
- No auth, no DB, no Docker, no queues — in-memory only
- Simple enough for a PM to explain in a Loom walkthrough

## Gotchas

- pytrends is frequently rate-limited on cloud IPs; search signal falls back to estimation from news frequency
- Reddit RSS requires a browser-like User-Agent header or it returns 429
- Port 8000 is the Python app; port 8080 is the (inactive) Node.js scaffold
