# ShareChat Trending Tags System

## Overview

This prototype is a lightweight trend-intelligence system designed for a Bharat-first social platform like [ShareChat](https://sharechat.com?utm_source=chatgpt.com).

It surfaces culturally relevant, high-momentum topics across entertainment, sports, politics, devotion, festivals, regional news, and creator culture by aggregating multiple public signals into a weighted ranking pipeline.

The system prioritises:

* fast discovery
* vernacular relevance
* trend freshness
* explainable ranking
* low-friction content exploration


---

# 1. How The System Decides What’s Trending

## Trend Sources

The system combines multiple public signals to identify topics rapidly gaining attention across India.

### A. Hindi Google News RSS

The system ingests Hindi-first and India-specific Google News RSS feeds across categories such as:

* sports/cricket
* Bollywood
* politics
* devotion/festivals
* business
* weather
* technology
* regional events

### B. Indian News Publishers

The system also prioritises high-volume Indian publishers popular among Tier-2/Tier-3 audiences, including:

* Aaj Tak
* ABP News
* Zee News
* India TV
* TV9 Bharatvarsh

These sources often capture mass-market conversations earlier than English-first outlets.

### C. Google Trends (India)

Google Trends is used as a high-confidence intent signal to identify what users are actively searching for, not just what publishers are covering.

### D. YouTube & Creator Signals

The system considers signals from Indian YouTube ecosystems including devotional, cricket, entertainment, music, and creator-led content.

This was important because a large share of vernacular internet consumption in India is video-first.

### E. Regional & Tier-2 Signals

The system intentionally includes region-aware signals from Tier-2/Tier-3 cities such as Indore, Lucknow, Patna, Surat, Jaipur, Kanpur, and Bhopal.


---

# Category Strategy

The system intentionally avoids over-indexing on only politics or entertainment.

Trending tags are distributed across categories such as:

* Cricket & Sports
* Bollywood & Entertainment
* Devotional/Festivals
* Politics
* Regional News
* Technology
* Creator/Meme Culture
* Weather & Public Events

This was done to better reflect actual Bharat browsing behaviour, where user engagement patterns are highly diverse and often culturally cyclical.

For example:

* devotional spikes during festivals
* cricket surges during IPL matches
* regional identity spikes during elections/weather/local incidents

---

# Trend Extraction Logic

The pipeline uses a lightweight rule-based topic extraction layer.

Incoming headlines and metadata are:

* tokenized
* normalized
* mapped against known trend entities
* grouped into canonical tags

Examples:

* “IPL”, “CSK”, “Dhoni” → Sports/Cricket cluster
* “Hanuman Jayanti”, “Mandir”, “Bhajan” → Devotional cluster

The system intentionally keeps tags:

* specific
* visually recognizable
* category-aligned
* easy to scan quickly

Instead of broad topics like:

* “Politics”

the system prefers:

* “Bihar Elections”
* “IPL 2026”
* “Salman Khan”
* “Mahakal Ujjain”

This improves click intent and feed clarity.

---

# Trend Scoring Logic

Each topic receives a weighted heat score.

## Scoring Signals

| Signal             | Purpose             | Weight |
| ------------------ | ------------------- | ------ |
| News Frequency     | Breadth of coverage | 35%    |
| Search Momentum    | Active user intent  | 25%    |
| Social/Video Buzz  | Viral spread        | 20%    |
| Regional Relevance | Tier-2 resonance    | 10%    |
| Recency Boost      | Freshness           | 10%    |

---

## Why These Weights?

### News Frequency (35%)

News coverage was weighted highest because it is the broadest and most stable signal source.

### Search Momentum (25%)

Google Trends acts as a strong confirmation signal for real-world user curiosity.

### Social & Video Buzz (20%)

This captures creator-led or grassroots internet momentum before mainstream coverage fully catches up.

### Regional Relevance (10%)

A smaller but important boost is given to topics showing strong regional clustering because ShareChat’s audience is highly geography-sensitive.

### Recency Boost (10%)

Fresh spikes are prioritised over older but still high-volume topics.

---

# Filtering & Quality Control

The pipeline applies several lightweight filtering steps before ranking.

## Filters Used

* duplicate keyword removal
* category normalization
* spam/noise filtering
* low-confidence trend removal
* minimum mention threshold
* profanity filtering
* stale trend suppression

The system also avoids over-clustering unrelated tags together to preserve trend clarity.

---

# 2. Workflow Diagram

```text
Raw Sources
(Google News, Google Trends, YouTube Signals,
Regional Publishers, Social Signals)
        │
        ▼
Content Fetch Layer
(RSS/API ingestion)
        │
        ▼
Keyword Extraction & Normalization
        │
        ▼
Category Mapping
(Sports / Politics / Devotional / Entertainment etc.)
        │
        ▼
Trend Scoring Engine
(Frequency + Momentum + Regional Weighting)
        │
        ▼
Deduplication & Filtering
        │
        ▼
Ranked Trending Tags
        │
        ▼
Frontend API
        │
        ▼
Horizontal Trending Cards UI
```

---

# 3. Models, APIs & Techniques Used

| Stage            | Technique/API                              | Why                                 |
| ---------------- | ------------------------------------------ | ----------------------------------- |
| News ingestion   | Google News RSS                            | Reliable real-time India coverage   |
| Search signal    | Google Trends / pytrends                   | Strong indicator of user intent     |
| Topic extraction | Rule-based keyword mapping + normalization | Lightweight and explainable         |
| Category mapping | Heuristic categorization                   | Fast iteration during prototyping   |
| Ranking          | Weighted heuristic scoring                 | Easier tuning without training data |
| Deduplication    | Fuzzy keyword matching                     | Reduces repeated tags               |
| Frontend         | React + Vite                               | Fast UI iteration                   |
| Backend API      | FastAPI                                    | Lightweight and easy deployment     |

The prototype intentionally uses explainable heuristics instead of heavy ML models because the goal was rapid prototyping, transparency, and fast experimentation.

---

# 4. UX Rationale

## Why Horizontal Trending Cards?

I chose horizontally scrollable visual cards instead of a dense text-only trending list.

This format worked better for:

* high-scroll mobile usage
* quick scanning behaviour
* entertainment-first browsing
* vernacular-first consumption patterns

The card format allows:

* larger visual hierarchy
* category cues
* easier discoverability
* better emotional immediacy

It also makes multiple topics visible simultaneously without overwhelming the screen vertically.

---

## Why Category-Aware Tags?

Users often consume trends differently based on intent:

* cricket during live matches
* devotion during festivals
* entertainment during casual browsing
* politics during major events

Adding category-awareness improves feed predictability and reduces cognitive load.

---

## Why Momentum Labels?

Labels such as:

* ⚡ Breaking
* 🔥 Rising

help communicate urgency immediately without requiring the user to open the feed.

This improves trend comprehension speed in low-attention browsing environments.

---

## What Was Considered & Rejected

### Rejected: Twitter/X-style text trend list

A compact list format was initially explored but rejected because it felt:

* too text-heavy
* less visually engaging
* weaker for entertainment browsing
* less suited for multilingual audiences

### Rejected: Overly Personalized Feed

The prototype intentionally avoids deep personalization at this stage because trend discovery should first establish broad social relevance before narrowing into individual preference loops.

---

# 5. What I’d Build With 4 More Weeks

| Priority | Improvement | Why |
|---|---|---|
| High | Geo-specific trend clusters | Surface different trends by state, city, and language region to better reflect hyperlocal Bharat consumption patterns |
| High | Creator & engagement signals | Incorporate shares, watch time, comment momentum, and creator engagement to better capture what is genuinely spreading on the platform |
| Medium | NLP-based topic extraction | Replace static keyword matching with smarter entity detection and Hindi language understanding to identify newer and emerging topics |
| Medium | Personalized trending tags | Adapt trending tags based on user behavior, language preferences, and engagement patterns instead of showing the same trends to every user |

