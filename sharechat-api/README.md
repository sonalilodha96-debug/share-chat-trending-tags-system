# ShareChat Trending Tags System

**APM Assignment — MVP Prototype**  
A FastAPI backend that identifies what is trending in India today for Hindi-speaking ShareChat users and returns a ranked list of 10 trending tags.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check — confirms API is running |
| `GET` | `/api/trends` | Returns top 10 trending tags as JSON |
| `GET` | `/debug/trends` | Renders trends as a clean HTML table (great for demos) |

---

## Data Sources

### 1. Google News India RSS
Category-specific RSS feeds from `news.google.com` with `hl=hi-IN&gl=IN&ceid=IN:hi`.  
Covers: General, Cricket/Sports, Bollywood, Politics, Business (Sensex/RBI), Weather/IMD, Festivals/Devotional, OTT/Entertainment, Tech/Startups.

**Why:** Google News aggregates thousands of Indian publishers in real time. It's the broadest and most reliable signal for what's making headlines in India right now.

### 2. Google Trends (via pytrends)
Fetches `trending_searches(pn='india')` — the top 20 searches happening in India at this moment.

**Why:** Search trends capture what's top-of-mind for users, not just what journalists write about. A topic trending here signals genuine user intent.

**Fallback:** If pytrends is rate-limited or blocked (common in hosted environments), the search signal is *estimated* from news frequency (topics with ≥3 news mentions get a 15-point estimated search score instead of 30). This is clearly marked in `sources[]`.

### 3. Reddit RSS (Social/Viral Proxy)
Public RSS feeds from: `r/india`, `r/bollywood`, `r/Cricket`, `r/IndianStreetBets`.

**Why:** Reddit captures grassroots viral content — topics spreading person-to-person before mainstream media picks them up. It's a useful proxy for the "social buzz" signal.

**Fallback:** If Reddit's RSS is unavailable, the social signal is simply 0 for that run. The API still returns results.

---

## Trend Pipeline Workflow

```
Call arrives at GET /api/trends
        │
        ├─► fetch_google_news()     → news_items (title, time, category)
        ├─► fetch_reddit()          → reddit_items (title, time)
        └─► fetch_google_trends()   → trend_keywords (list of strings)
                │
                ▼
        extract_topics()
          • Scans every title for 60+ known keywords (KEYWORD_TO_TAG map)
          • Builds: keyword → {news_count, social_count, search_hit, earliest_dt, sources}
                │
                ▼
        compute_score()  (per keyword)
          • news signal:    min(news_count × 5, 40)
          • search signal:  30 if in Trends | 15 if estimated | 0
          • social signal:  min(social_count × 5, 20)
          • recency signal: 10 if < 6h | 5 if < 24h | 0
          • total:          min(sum, 100)
                │
                ▼
        build_trends()
          • Sort by heatScore descending
          • Pad to 10 using FALLBACK_TOPICS if needed
          • Assign rank 1–10
          • Return structured JSON
```

---

## Scoring Formula

```
heatScore = min(
  news_signal    +   // max 40: breadth of mainstream coverage
  search_signal  +   // max 30: confirmed user search intent
  social_signal  +   // max 20: viral/social buzz
  recency_signal,    // max 10: freshness bonus
  100
)

news_signal    = min(news_mention_count × 5, 40)
search_signal  = 30 if keyword found in Google Trends
                 15 if pytrends unavailable but news_count ≥ 3  (estimated)
                 0  otherwise
social_signal  = min(reddit_mention_count × 5, 20)
recency_signal = 10 if first mention < 6 hours ago
                 5  if first mention < 24 hours ago
                 0  otherwise
```

**Why these weights?**
- News (40) is the biggest signal because it's the most data-rich and reliable source for India.
- Search (30) is the gold standard for user intent but is a single boolean per topic.
- Social (20) catches grassroots virality not yet in mainstream news.
- Recency (10) is a tiebreaker that favours fresh stories over stale ones with high counts.

---

## Momentum Labels

| Label | Condition |
|-------|-----------|
| ⚡ Breaking | Topic appeared < 2 hours ago |
| 🔥 Rising | heatScore ≥ 60 or total mentions ≥ 5 |
| 🟢 New | Default / emerging trend |

---

## Known Limitations

1. **pytrends rate limiting** — Google aggressively blocks automated Trends access from cloud IPs. The estimated fallback (15 pts from news frequency) is a reasonable proxy but not identical to real search volume.
2. **Keyword map is finite** — The system can only detect topics it knows about. A brand-new proper noun (e.g. a new politician's name) won't appear until added to `KEYWORD_TO_TAG`.
3. **No deduplication of near-synonyms** — "film" and "movie" are counted separately. A merge step would reduce noise.
4. **Reddit is English-heavy** — Most Reddit India posts are in English, which actually helps keyword matching but doesn't reflect the Hindi-first ShareChat audience perfectly.
5. **No historical context** — The system has no memory of what was trending yesterday, so it can't distinguish "newly rising" from "always present" topics.
6. **Sequential fetching** — All three sources are fetched one after another. Latency adds up (~3–8 seconds per call).
7. **Post count is estimated** — The `postCount` field is a formula-based estimate, not a real database query.

---

## What Would Be Improved With 4 More Weeks

| Priority | Improvement |
|----------|-------------|
| 🔴 High | **Caching layer** (Redis TTL ~15 min) — avoid re-fetching on every call, reduce latency from ~5s to ~50ms |
| 🔴 High | **Parallel fetching** — use `asyncio.gather()` to fetch all sources simultaneously; cuts latency by ~60% |
| 🔴 High | **Real ShareChat data signal** — integrate internal post/view/share counts from ShareChat's own analytics pipeline |
| 🟡 Medium | **NLP-based topic extraction** — replace keyword map with NER (spaCy/indic-nlp) to catch novel topics and proper nouns |
| 🟡 Medium | **Hindi language support in extraction** — parse Devanagari headlines directly, not just English keywords |
| 🟡 Medium | **Trending velocity** — compare current score to rolling 7-day average; surface topics that are *newly* spiking |
| 🟡 Medium | **Category confidence scoring** — use a classifier instead of keyword heuristics for more accurate categorization |
| 🟢 Low | **Admin dashboard** — real-time view of pipeline health, source success rates, and score distributions |
| 🟢 Low | **A/B testing hook** — expose a `variant` param to test different scoring weights |
| 🟢 Low | **Webhook alerts** — push ⚡ Breaking trends to Slack/Teams when heatScore > 80 |

---

## Running Locally

```bash
cd sharechat-api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Then visit:
- `http://localhost:8000/` — health check
- `http://localhost:8000/api/trends` — JSON trends
- `http://localhost:8000/debug/trends` — visual HTML table
