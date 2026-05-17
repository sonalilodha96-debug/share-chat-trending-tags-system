# ShareChat Trending Tags System

**APM Assignment - MVP Prototype**  
A FastAPI backend that identifies what is trending in India today for Hindi-speaking ShareChat users and returns a ranked list of 10 trending tags.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check — confirms API is running |
| `GET` | `/api/trends` | Returns top 10 trending tags as JSON |
| `GET` | `/debug/trends` | Renders trends as a clean HTML table (great for demos) |

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

---

## Momentum Labels

| Label | Condition |
|-------|-----------|
| ⚡ Breaking | Topic appeared < 2 hours ago |
| 🔥 Rising | heatScore ≥ 60 or total mentions ≥ 5 |
| 🟢 New | Default / emerging trend |

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
