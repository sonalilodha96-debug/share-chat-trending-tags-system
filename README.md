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

## Trend Sources

The system combines multiple public signals to identify topics rapidly gaining attention across India.

| Source | Coverage |
|---|---|
| Hindi Google News RSS | Tracks India-specific trends across sports, Bollywood, politics, devotion/festivals, business, weather, technology, and regional events |
| Indian news publishers (Aaj Tak, ABP, Zee, India TV, TV9 Bharatvarsh) | Captures fast-moving mass-market conversations popular among Tier-2/Tier-3 audiences |
| Google Trends (India) | Identifies active search momentum and real-world user curiosity |
| YouTube & creator signals | Captures momentum from devotional, cricket, entertainment, music, and creator-led video ecosystems |
| Regional & Tier-2 signals | Surfaces trends resonating across cities such as Indore, Lucknow, Patna, Surat, Jaipur, Kanpur, and Bhopal |

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

| Signal | Weight | Why It Matters |
|---|---|---|
| News Frequency | 35% | News coverage is the broadest and most stable signal source for identifying large-scale conversations across India |
| Search Momentum | 25% | Google Trends acts as a strong confirmation signal for real-world user curiosity and active search intent |
| Social/Video Buzz | 20% | Captures creator-led and grassroots internet momentum before mainstream coverage fully catches up |
| Regional Relevance | 10% | Gives additional importance to topics strongly resonating across Tier-2/Tier-3 regions and language clusters |
| Recency Boost | 10% | Prioritises fresh spikes and emerging conversations over older but still high-volume topics |
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

## UX Rationale

| Design Choice | Rationale |
|---|---|
| Horizontal trending cards | Better suited for high-scroll mobile usage, quick scanning behaviour, and entertainment-first browsing patterns |
| Visual-first layout | Improves discoverability and allows users to identify trends faster through imagery and category cues |
| Category-aware tags | Helps users navigate different intent states such as cricket, devotion, entertainment, or politics more predictably |
| Momentum labels (⚡ Breaking, 🔥 Rising) | Communicates freshness and urgency instantly without requiring users to open the feed |
| Limited tags per screen | Prevents cognitive overload while still surfacing multiple trend categories simultaneously |
| Rejected dense text-only lists | A Twitter/X-style format felt too text-heavy and less engaging for vernacular-first consumption patterns |


## What Was Considered & Rejected

A compact list format was initially explored but rejected because it felt:

* too text-heavy
* less visually engaging
* weaker for entertainment browsing
* less suited for multilingual audiences


---

# 5. What I’d Build With 4 More Weeks

| Priority | Improvement | Why |
|---|---|---|
| High | Geo-specific trend clusters | Surface different trends by state, city, and language region to better reflect hyperlocal Bharat consumption patterns |
| High | Creator & engagement signals | Incorporate shares, watch time, comment momentum, and creator engagement to better capture what is genuinely spreading on the platform |
| Medium | NLP-based topic extraction | Replace static keyword matching with smarter entity detection and Hindi language understanding to identify newer and emerging topics |
| Medium | Personalized trending tags | Adapt trending tags based on user behavior, language preferences, and engagement patterns instead of showing the same trends to every user |

