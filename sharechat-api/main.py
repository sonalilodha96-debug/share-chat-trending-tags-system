"""
ShareChat Trending Tags System — FastAPI Backend
APM Assignment MVP | In-memory processing, no auth, no DB

Pipeline:
  1. Fetch   → Google News RSS + Google Trends (pytrends) + Reddit RSS
  2. Extract → parse titles for candidate topics using keyword matching
  3. Clean   → remove noise, normalize keywords
  4. Tag     → convert to Hindi/Hinglish hashtags
  5. Dedupe  → keyword map handles deduplication implicitly
  6. Score   → weighted heat score (news 40 + search 30 + social 20 + recency 10)
  7. Sort    → top 10 by score
  8. Return  → full metadata for UI rendering

Author: APM Candidate
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

import feedparser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# ─── App setup ───────────────────────────────────────────────────────────────

app = FastAPI(title="ShareChat Trending Tags API", version="1.0.0")

# CORS: allow Lovable frontend (or any origin) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Google News RSS Feed URLs (India, Hindi) ────────────────────────────────
# Each category gets its own targeted feed to ensure breadth of coverage.

GOOGLE_NEWS_FEEDS = {
    "general":       "https://news.google.com/rss?hl=hi-IN&gl=IN&ceid=IN:hi",
    "cricket":       "https://news.google.com/rss/search?q=cricket+india+match&hl=hi-IN&gl=IN&ceid=IN:hi",
    "ipl":           "https://news.google.com/rss/search?q=IPL+2025+match&hl=hi-IN&gl=IN&ceid=IN:hi",
    "bollywood":     "https://news.google.com/rss/search?q=bollywood+film+release&hl=hi-IN&gl=IN&ceid=IN:hi",
    "bhojpuri":      "https://news.google.com/rss/search?q=bhojpuri+song+film&hl=hi-IN&gl=IN&ceid=IN:hi",
    "politics":      "https://news.google.com/rss/search?q=india+politics+election&hl=hi-IN&gl=IN&ceid=IN:hi",
    "business":      "https://news.google.com/rss/search?q=sensex+nifty+rupee+RBI&hl=hi-IN&gl=IN&ceid=IN:hi",
    "weather":       "https://news.google.com/rss/search?q=weather+rain+India+IMD+city&hl=hi-IN&gl=IN&ceid=IN:hi",
    "devotional":    "https://news.google.com/rss/search?q=festival+puja+vrat+temple+india&hl=hi-IN&gl=IN&ceid=IN:hi",
    "entertainment": "https://news.google.com/rss/search?q=OTT+web+series+netflix+india&hl=hi-IN&gl=IN&ceid=IN:hi",
    "tech":          "https://news.google.com/rss/search?q=startup+app+india+tech+AI&hl=hi-IN&gl=IN&ceid=IN:hi",
    "exam_jobs":     "https://news.google.com/rss/search?q=sarkari+naukri+SSC+UPSC+exam+result+UP+Bihar&hl=hi-IN&gl=IN&ceid=IN:hi",
    "viral":         "https://news.google.com/rss/search?q=viral+video+reel+india+trending&hl=hi-IN&gl=IN&ceid=IN:hi",
    "local_up":      "https://news.google.com/rss/search?q=UP+Lucknow+Varanasi+Prayagraj+Kanpur&hl=hi-IN&gl=IN&ceid=IN:hi",
    # ── Google News Hindi-language topic feeds (aggregates all Hindi publishers)
    "hi_top":        "https://news.google.com/rss/headlines/section/topic/NATION?hl=hi&gl=IN&ceid=IN:hi",
    "hi_politics":   "https://news.google.com/rss/headlines/section/topic/POLITICS?hl=hi&gl=IN&ceid=IN:hi",
    "hi_sports":     "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=hi&gl=IN&ceid=IN:hi",
    "hi_entertain":  "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=hi&gl=IN&ceid=IN:hi",
    "hi_tech":       "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=hi&gl=IN&ceid=IN:hi",
    "hi_business":   "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=hi&gl=IN&ceid=IN:hi",
    "hi_health":     "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=hi&gl=IN&ceid=IN:hi",
}

# ─── Direct Hindi News RSS Feeds ─────────────────────────────────────────────
# Sources verified to return RSS without blocking cloud IPs.
# Titles are in Hindi, giving direct signal from Tier-2/Bharat audience.

HINDI_DIRECT_FEEDS = {
    "Amar Ujala":      "https://www.amarujala.com/rss/india-news.xml",
    "Dainik Bhaskar":  "https://www.bhaskar.com/rss-feed/1061/",
}

# ─── Reddit RSS Feeds ────────────────────────────────────────────────────────
# Public subreddits with India-relevant content act as a social/viral proxy.

REDDIT_FEEDS = [
    "https://www.reddit.com/r/india/.rss",
    "https://www.reddit.com/r/bollywood/.rss",
    "https://www.reddit.com/r/Cricket/.rss",
    "https://www.reddit.com/r/IndianStreetBets/.rss",
]

# ─── YouTube Channel RSS Feeds ───────────────────────────────────────────────
# Public YouTube channel feeds work without any API key.
# Format: https://www.youtube.com/feeds/videos.xml?channel_id=<ID>
# These major Indian channels cover cricket, Bollywood, devotional, comedy,
# TV serials, and viral content — giving a strong Bharat-specific social signal.

YOUTUBE_CHANNELS = {
    # ── RSS-verified channels (tested and confirmed working) ─────────────────
    "T-Series":   "UCq-Fj5jknLsUf-MWSy4_brA",  # Bollywood music — India's #1 channel
    "SET India":  "UCpEhnqL0y41EpW2TvWAHD7Q",  # Sony TV serials (KBC, Bigg Boss, etc.)
    "Zee Music":  "UCFFbwnve3yF62-tVXkTyHqg",  # Zee Bollywood/music
    "Aaj Tak":    "UCt4t-jeY85JegMlZ-E5UWtA",  # Hindi news — strong Bharat signal
    "NDTV India": "UCZFMm1mMw0F81Z37aaEzTUA",  # Hindi news — national/political
}

# ─── Keyword → (Hindi Tag, Hindi Category, English Category Key) ─────────────
# This map drives extraction, tagging, and categorization all in one place.
# Keys are lowercase English keywords found in news/reddit headlines.

KEYWORD_TO_TAG = {
    # ── खेल (Sports) ──
    "cricket":        ("#क्रिकेट",      "खेल",       "sports"),
    "ipl":            ("#आईपीएल",       "खेल",       "sports"),
    "virat":          ("#विराट",         "खेल",       "sports"),
    "rohit":          ("#रोहित",         "खेल",       "sports"),
    "world cup":      ("#वर्ल्डकप",     "खेल",       "sports"),
    "kabaddi":        ("#कबड्डी",       "खेल",       "sports"),
    "football":       ("#फुटबॉल",       "खेल",       "sports"),
    "hockey":         ("#हॉकी",          "खेल",       "sports"),
    "badminton":      ("#बैडमिंटन",     "खेल",       "sports"),

    # ── मनोरंजन (Entertainment) ──
    "bollywood":      ("#बॉलीवुड",      "मनोरंजन",   "entertainment"),
    "film":           ("#फ़िल्म",        "मनोरंजन",   "entertainment"),
    "movie":          ("#मूवी",          "मनोरंजन",   "entertainment"),
    "ott":            ("#OTT",           "मनोरंजन",   "entertainment"),
    "netflix":        ("#Netflix",       "मनोरंजन",   "entertainment"),
    "series":         ("#वेबसीरीज",     "मनोरंजन",   "entertainment"),
    "salman":         ("#सलमान",         "मनोरंजन",   "entertainment"),
    "shahrukh":       ("#शाहरुख",       "मनोरंजन",   "entertainment"),
    "deepika":        ("#दीपिका",        "मनोरंजन",   "entertainment"),
    "ranveer":        ("#रणवीर",         "मनोरंजन",   "entertainment"),
    "alia":           ("#आलिया",         "मनोरंजन",   "entertainment"),
    "akshay":         ("#अक्षय",         "मनोरंजन",   "entertainment"),

    # ── समाचार (News / Politics) ──
    "modi":           ("#मोदी",          "समाचार",    "news"),
    "election":       ("#चुनाव",         "समाचार",    "news"),
    "parliament":     ("#संसद",          "समाचार",    "news"),
    "bjp":            ("#भाजपा",         "समाचार",    "news"),
    "congress":       ("#कांग्रेस",      "समाचार",    "news"),
    "rahul":          ("#राहुल",         "समाचार",    "news"),
    "supreme court":  ("#सुप्रीमकोर्ट", "समाचार",    "news"),
    "government":     ("#सरकार",         "समाचार",    "news"),
    "protest":        ("#विरोध",         "समाचार",    "news"),
    "army":           ("#सेना",          "समाचार",    "news"),

    # ── बिजनेस (Business) ──
    "sensex":         ("#सेंसेक्स",     "बिजनेस",    "business"),
    "nifty":          ("#निफ्टी",        "बिजनेस",    "business"),
    "rbi":            ("#RBI",           "बिजनेस",    "business"),
    "rupee":          ("#रुपया",          "बिजनेस",    "business"),
    "startup":        ("#स्टार्टअप",    "बिजनेस",    "business"),
    "share market":   ("#शेयरबाजार",    "बिजनेस",    "business"),
    "bitcoin":        ("#Bitcoin",       "बिजनेस",    "business"),
    "inflation":      ("#महंगाई",        "बिजनेस",    "business"),
    "petrol":         ("#पेट्रोल",       "बिजनेस",    "business"),
    "budget":         ("#बजट",           "बिजनेस",    "business"),

    # ── मौसम (Weather) ──
    "weather":        ("#मौसम",          "मौसम",       "weather"),
    "rain":           ("#बारिश",          "मौसम",       "weather"),
    "flood":          ("#बाढ़",           "मौसम",       "weather"),
    "heatwave":       ("#गर्मी",          "मौसम",       "weather"),
    "cyclone":        ("#चक्रवात",       "मौसम",       "weather"),
    "imd":            ("#IMD",            "मौसम",       "weather"),
    "monsoon":        ("#मानसून",         "मौसम",       "weather"),

    # ── भक्ति (Devotional) ──
    "temple":         ("#मंदिर",          "भक्ति",     "devotional"),
    "puja":           ("#पूजा",           "भक्ति",     "devotional"),
    "festival":       ("#त्योहार",       "भक्ति",     "devotional"),
    "diwali":         ("#दीवाली",         "भक्ति",     "devotional"),
    "navratri":       ("#नवरात्रि",      "भक्ति",     "devotional"),
    "eid":            ("#ईद",             "भक्ति",     "devotional"),
    "ram":            ("#राम",            "भक्ति",     "devotional"),
    "krishna":        ("#कृष्ण",         "भक्ति",     "devotional"),
    "hanuman":        ("#हनुमान",         "भक्ति",     "devotional"),

    # ── टेक (Tech) ──
    "ai":             ("#AI",             "टेक",        "tech"),
    "chatgpt":        ("#ChatGPT",        "टेक",        "tech"),
    "jio":            ("#Jio",            "टेक",        "tech"),
    "5g":             ("#5G",             "टेक",        "tech"),
    "iphone":         ("#iPhone",         "टेक",        "tech"),
    "android":        ("#Android",        "टेक",        "tech"),
    "google":         ("#Google",         "टेक",        "tech"),

    # ── लोकल (Local India) ──
    "delhi":          ("#दिल्ली",         "लोकल",      "local"),
    "mumbai":         ("#मुंबई",          "लोकल",      "local"),
    "uttar pradesh":  ("#उत्तरप्रदेश",  "लोकल",      "local"),
    "maharashtra":    ("#महाराष्ट्र",    "लोकल",      "local"),
    "punjab":         ("#पंजाब",          "लोकल",      "local"),
    "rajasthan":      ("#राजस्थान",      "लोकल",      "local"),
    "bengaluru":      ("#बेंगलुरु",      "लोकल",      "local"),
    "kashmir":        ("#कश्मीर",         "लोकल",      "local"),
    "varanasi":       ("#वाराणसी",       "लोकल",      "local"),
    "prayagraj":      ("#प्रयागराज",     "लोकल",      "local"),
    "kumbh":          ("#कुंभमेला",      "लोकल",      "local"),
    "lucknow":        ("#लखनऊ",          "लोकल",      "local"),
    "kanpur":         ("#कानपुर",         "लोकल",      "local"),
    "patna":          ("#पटना",           "लोकल",      "local"),
    "indore":         ("#इंदौर",          "लोकल",      "local"),
    "bhopal":         ("#भोपाल",          "लोकल",      "local"),
    "ranchi":         ("#रांची",          "लोकल",      "local"),
    "raipur":         ("#रायपुर",         "लोकल",      "local"),
    "meerut":         ("#मेरठ",           "लोकल",      "local"),
    "agra":           ("#आगरा",           "लोकल",      "local"),
    "gorakhpur":      ("#गोरखपुर",       "लोकल",      "local"),
    "jaipur":         ("#जयपुर",          "लोकल",      "local"),

    # ── परीक्षा / नौकरी (Exam / Jobs) ──
    "ssc":            ("#SSCपरीक्षा",    "परीक्षा",   "exam"),
    "upsc":           ("#UPSCपरीक्षा",  "परीक्षा",   "exam"),
    "board result":   ("#बोर्डरिजल्ट",  "परीक्षा",   "exam"),
    "up board":       ("#UPBoardResult", "परीक्षा",   "exam"),
    "bihar board":    ("#BiharBoard",    "परीक्षा",   "exam"),
    "sarkari naukri": ("#सरकारीनौकरी", "नौकरी",     "jobs"),
    "vacancy":        ("#सरकारीभर्ती",  "नौकरी",     "jobs"),
    "recruitment":    ("#भर्ती",          "नौकरी",     "jobs"),

    # ── वायरल / मनोरंजन (Viral / Comedy) ──
    "viral":          ("#वायरलवीडियो",  "वायरल",     "viral"),
    "reel":           ("#ReelViral",     "वायरल",     "viral"),
    "meme":           ("#वायरलमीम्स",  "वायरल",     "viral"),
    "comedy":         ("#कॉमेडीवीडियो","वायरल",     "viral"),

    # ── भोजपुरी / क्षेत्रीय (Bhojpuri / Regional) ──
    "bhojpuri":       ("#भोजपुरीगाना", "मनोरंजन",  "entertainment"),
    "haryanvi":       ("#हरियाणवीगाना","मनोरंजन",  "entertainment"),

    # ── त्योहार / भक्ति विस्तार (Festival Extension) ──
    "sawan":          ("#सावनसोमवार",  "भक्ति",     "devotional"),
    "shravan":        ("#सावनसोमवार",  "भक्ति",     "devotional"),
    "chhath":         ("#छठपूजा",       "भक्ति",     "devotional"),
    "teej":           ("#तीज",           "भक्ति",     "devotional"),
    "karva chauth":   ("#करवाचौथ",     "भक्ति",     "devotional"),
    "vrat":           ("#व्रत",          "भक्ति",     "devotional"),
    "ayodhya":        ("#राममंदिर",     "भक्ति",     "devotional"),
    "ram mandir":     ("#राममंदिर",     "भक्ति",     "devotional"),
    "mahakumbh":      ("#महाकुंभ",      "भक्ति",     "devotional"),

    # ── सरकारी योजना (Government Schemes) ──
    "yojana":         ("#सरकारीयोजना","समाचार",    "news"),
    "scheme":         ("#सरकारीयोजना","समाचार",    "news"),
    "pm modi":        ("#PMमोदी",        "समाचार",    "news"),
}

# ─── Context lookup tables for tag refinement ────────────────────────────────
# These are ONLY used by refine_tag() — they have no effect on keyword matching
# or scoring. They let us upgrade a generic tag to a specific 2-3 word tag.

CITY_HINDI = {
    # Metro cities
    "delhi": "दिल्ली", "new delhi": "दिल्ली",
    "mumbai": "मुंबई", "bombay": "मुंबई",
    "chennai": "चेन्नई", "madras": "चेन्नई",
    "kolkata": "कोलकाता", "calcutta": "कोलकाता",
    "bengaluru": "बेंगलुरु", "bangalore": "बेंगलुरु",
    "hyderabad": "हैदराबाद",
    "ahmedabad": "अहमदाबाद",
    "pune": "पुणे",
    # Tier-2 Hindi belt
    "lucknow": "लखनऊ",
    "kanpur": "कानपुर",
    "varanasi": "वाराणसी", "banaras": "वाराणसी",
    "prayagraj": "प्रयागराज", "allahabad": "प्रयागराज",
    "gorakhpur": "गोरखपुर",
    "meerut": "मेरठ",
    "agra": "आगरा",
    "jaipur": "जयपुर",
    "indore": "इंदौर",
    "bhopal": "भोपाल",
    "patna": "पटना",
    "ranchi": "रांची",
    "raipur": "रायपुर",
    "chandigarh": "चंडीगढ़",
    "nagpur": "नागपुर",
    "surat": "सूरत",
    "nashik": "नाशिक",
    "coimbatore": "कोयंबटूर",
    # States / regions
    "kerala": "केरल",
    "gujarat": "गुजरात",
    "rajasthan": "राजस्थान",
    "assam": "असम",
    "odisha": "ओडिशा",
    "uttarakhand": "उत्तराखंड",
    "himachal": "हिमाचल",
    "kashmir": "कश्मीर",
    "goa": "गोवा",
    "haryana": "हरियाणा",
    "jharkhand": "झारखंड",
    "chhattisgarh": "छत्तीसगढ़",
    "bihar": "बिहार",
    "mp": "MP",
}

CRICKET_TEAMS = {
    "australia": "ऑस्ट्रेलिया",
    "england": "इंग्लैंड",
    "pakistan": "पाकिस्तान",
    "south africa": "साउथअफ्रीका",
    "new zealand": "न्यूजीलैंड",
    "west indies": "वेस्टइंडीज",
    "sri lanka": "श्रीलंका",
    "bangladesh": "बांग्लादेश",
    "afghanistan": "अफगानिस्तान",
    "zimbabwe": "जिम्बाब्वे",
}

IPL_TEAMS = {
    "chennai super kings": "CSK", "csk": "CSK",
    "mumbai indians": "MI", " mi ": "MI",
    "royal challengers": "RCB", "rcb": "RCB",
    "kolkata knight": "KKR", "kkr": "KKR",
    "delhi capitals": "DC", " dc ": "DC",
    "sunrisers": "SRH", "srh": "SRH",
    "rajasthan royals": "RR", " rr ": "RR",
    "punjab kings": "PBKS", "pbks": "PBKS",
    "lucknow super": "LSG", "lsg": "LSG",
    "gujarat titans": "GT", " gt ": "GT",
}

AI_CONTEXTS = {
    "video":    "वीडियो",
    "deepfake": "डीपफेक",
    "homework": "होमवर्क",
    "exam":     "एग्जाम",
    "voice":    "वॉयस",
    "chatbot":  "चैटबॉट",
    "job":      "नौकरी",
    "jobs":     "नौकरी",
    "fraud":    "फ्रॉड",
    "scam":     "फ्रॉड",
    "art":      "आर्ट",
    "image":    "इमेज",
    "search":   "सर्च",
    "robot":    "रोबोट",
    "model":    "मॉडल",
}

# Title-case words to ignore when scanning for show/movie/entity names
_SKIP_WORDS = {
    "The", "A", "An", "In", "On", "At", "To", "Is", "Are", "Was", "Will",
    "And", "Or", "But", "For", "With", "Of", "From", "By", "As", "Be",
    "Has", "Have", "Had", "Do", "Does", "Did", "Not", "No", "Can", "Could",
    "Get", "Got", "Its", "It", "He", "She", "They", "We", "You", "His", "Her",
    "How", "Why", "What", "When", "Where", "Who", "New", "Big", "All", "Now",
    "Over", "After", "Before", "This", "That", "These", "Those", "First", "Last",
    "India", "Indian", "Hindi", "Season", "Web", "Series", "Film", "Movie",
    "Episode", "Watch", "Stream", "Platform", "Release", "Date", "Out", "Review",
    "Bollywood", "Actor", "Actress", "Director", "Box", "Office", "Collection",
    "Report", "Says", "Know", "Here", "Check", "Latest", "News", "Today",
    # Headline verbs that appear Title-Case but aren't entity names
    "Release", "Releases", "Released", "Releasing", "Coming", "Upcoming", "Arrives",
    "Watch", "Available", "Stars", "Makes", "Gets", "Sets", "Hits", "Tops",
    "Wins", "Drops", "Rises", "Falls", "Opens", "Breaks", "Takes", "Shows",
    "Reveals", "Announces", "Launches", "Returns", "Premiere", "Premieres",
    "Trailer", "Teaser", "Poster", "Cast", "Crew", "Budget", "Flop", "Hit",
    "Part", "Chapter", "Volume", "Edition", "Update", "Version", "Season",
    # Streaming platform names — never use these as the "show title"
    "Netflix", "Amazon", "Prime", "Disney", "Hotstar", "Zee5", "Sonyliv",
    "Jiocinema", "Mubi", "Ott", "Streaming", "Youtube", "Jio",
    # Common tech/company noise
    "Google", "Apple", "Microsoft", "Meta", "Twitter", "Instagram",
    "Whatsapp", "Facebook", "Tiktok", "Snapchat", "Openai", "Chatgpt",
    # News publisher / channel names — must never become part of a hashtag
    "News18", "News24", "Ndtv", "Aajtak", "AajTak", "Zeenews", "ZeeNews",
    "Abpnews", "AbpNews", "Abp", "Tv9", "IndiaTV", "Indiatv",
    "Bharatvarsh", "Bharat", "Jagran", "Bhaskar", "Amarujala", "Hindustan",
    "Patrika", "Livemint", "Mint", "Hindu", "Times", "Tribune",
}


def sanitize_tag(tag: str) -> str:
    """
    Remove doubled tokens inside a compound hashtag.

    Catches patterns like #NetflixNetflix, #AIAI, #OTTरिलीजOTT that can
    arise when both the keyword and the derived context share the same word.

    Strategy:
      1. If the bare content (without #) is an exact N-fold repetition, keep
         only one copy.  e.g. "NetflixNetflix" → "Netflix"
      2. If an ASCII word of ≥3 chars is immediately repeated at the end of
         the content, remove the duplicate.  e.g. "IndiaAIAI" → "IndiaAI"
    """
    content = tag.lstrip("#")
    if not content:
        return tag

    # Check whole-string doubling (case-insensitive): "XyzXyz" → "Xyz"
    n = len(content)
    for divisor in range(1, n // 2 + 1):
        if n % divisor == 0:
            chunk = content[:divisor]
            if chunk.lower() * (n // divisor) == content.lower():
                return "#" + content[:divisor]

    # Check trailing repeated ASCII token (≥2 chars): "IndiaAIAI" → "IndiaAI"
    m = re.search(r'([A-Za-z]{2,})\1$', content, re.IGNORECASE)
    if m:
        dup = m.group(1)
        # Remove the second occurrence only
        idx = content.rfind(dup)
        return "#" + content[:idx]

    return tag


def _find_proper_noun(titles: list[str], min_len: int = 4) -> str | None:
    """Extract the first Title-Case proper noun from headlines, skipping noise words."""
    for title in titles:
        matches = re.findall(r'\b([A-Z][a-zA-Z0-9]+)\b', title)
        for word in matches:
            if word not in _SKIP_WORDS and len(word) >= min_len:
                return word
    return None


def refine_tag(keyword: str, base_tag: str, sample_titles: list[str]) -> str:
    """
    Upgrade a generic base_tag to a specific 2-3 word hashtag using headline context.

    Strategy: look for location, person, event, show/movie title, or policy cue
    in sample_titles and combine with the topic to form a precise tag.

    Falls back to base_tag when no useful context can be extracted.
    This function must never raise — all exceptions return base_tag.
    """
    try:
        combined = " ".join(sample_titles).lower()

        # ── Weather / IMD ─────────────────────────────────────────────────────
        if keyword in ("imd", "weather", "rain", "monsoon", "heatwave", "flood", "cyclone"):
            if keyword == "cyclone":
                m = re.search(r"[Cc]yclone\s+([A-Z][a-z]+)", " ".join(sample_titles))
                if m:
                    return f"#{m.group(1)}चक्रवात"
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    if keyword in ("rain", "monsoon"):
                        return f"#{city_hi}बारिश"
                    if keyword == "heatwave":
                        return f"#{city_hi}गर्मी"
                    if keyword == "flood":
                        return f"#{city_hi}बाढ़"
                    if keyword == "imd":
                        return f"#{city_hi}IMDअलर्ट"
                    if keyword == "weather":
                        return f"#{city_hi}मौसम"
            if keyword == "imd":
                if any(w in combined for w in ("alert", "warning", "red")):
                    return "#IMDअलर्ट"
                if any(w in combined for w in ("forecast", "predict")):
                    return "#मौसमपूर्वानुमान"
            return base_tag

        # ── OTT / Netflix / Series ─────────────────────────────────────────────
        if keyword in ("ott", "netflix", "series"):
            # Look for streaming platform cues
            platform_map = {
                "amazon prime": "Prime", "prime video": "Prime",
                "disney+": "Disney", "hotstar": "Hotstar",
                "zee5": "Zee5", "sonyliv": "SonyLiv",
                "jiocinema": "JioCinema", "jio cinema": "JioCinema",
                "mubi": "Mubi",
            }
            for plat_en, plat_tag in platform_map.items():
                if plat_en in combined:
                    proper = _find_proper_noun(sample_titles)
                    if proper:
                        return f"#{proper}{plat_tag}"
                    return f"#{plat_tag}OTTरिलीज"
            # Try to extract a show/movie title
            proper = _find_proper_noun(sample_titles)
            if proper:
                suffix = "Netflix" if keyword == "netflix" else "OTT"
                return f"#{proper}{suffix}"
            return "#OTTरिलीज"

        # ── AI ────────────────────────────────────────────────────────────────
        if keyword == "ai":
            # Specific AI product names first
            for prod in [("grok", "Grok"), ("gemini", "Gemini"), ("claude", "Claude"),
                         ("perplexity", "Perplexity"), ("openai", "OpenAI"),
                         ("sora", "Sora"), ("copilot", "Copilot"), ("llama", "Llama"),
                         ("chatgpt", "ChatGPT"), ("bard", "Bard"), ("midjourney", "MJ")]:
                if prod[0] in combined:
                    return f"#{prod[1]}AI"
            # Use-case context (existing dict)
            for ctx_en, ctx_hi in AI_CONTEXTS.items():
                if ctx_en in combined:
                    return f"#AI{ctx_hi}"
            # Broader India-specific context
            if any(w in combined for w in ("student", "school", "college", "education", "class")):
                return "#AIएजुकेशन"
            if any(w in combined for w in ("policy", "regulation", "law", "rule", "government", "ministry")):
                return "#AIनीति"
            if any(w in combined for w in ("startup", "funding", "invest", "crore", "billion", "unicorn")):
                return "#AIस्टार्टअप"
            if any(w in combined for w in ("health", "doctor", "hospital", "medicine", "disease")):
                return "#AIहेल्थ"
            if any(w in combined for w in ("jio", "reliance", "tata", "infosys", "wipro", "tcs")):
                proper = _find_proper_noun(sample_titles)
                if proper and proper not in _SKIP_WORDS:
                    return f"#{proper}AI"
            if "india" in combined:
                return "#IndiaAI"
            return "#AIटेक"

        # ── Cricket ───────────────────────────────────────────────────────────
        if keyword == "cricket":
            for team_en, team_hi in CRICKET_TEAMS.items():
                if team_en in combined:
                    return f"#IndVs{team_hi}"
            if "test" in combined:
                return "#IndiaTest"
            if "t20" in combined or "t-20" in combined:
                return "#IndiaT20"
            if "odi" in combined:
                return "#IndiaODI"
            return base_tag

        # ── IPL ───────────────────────────────────────────────────────────────
        if keyword == "ipl":
            for team_en, team_abbr in IPL_TEAMS.items():
                if team_en in combined:
                    return f"#IPL{team_abbr}"
            if "final" in combined:
                return "#IPLफाइनल"
            if "playoff" in combined or "qualifier" in combined:
                return "#IPLप्लेऑफ"
            if "auction" in combined:
                return "#IPLनीलामी"
            return base_tag

        # ── Bollywood / Film / Movie ──────────────────────────────────────────
        if keyword in ("bollywood", "film", "movie"):
            proper = _find_proper_noun(sample_titles, min_len=5)
            if proper:
                return f"#{proper}मूवी"
            return base_tag

        # ── Modi ─────────────────────────────────────────────────────────────
        if keyword == "modi":
            country_map = {
                "america": "अमेरिका", "usa": "अमेरिका", " us ": "अमेरिका",
                "russia": "रूस", "china": "चीन", "japan": "जापान",
                "saudi": "सऊदी", "france": "फ्रांस", "germany": "जर्मनी",
                "uk": "UK", "israel": "इजराइल", "iran": "ईरान",
                "ukraine": "यूक्रेन", "pakistan": "पाकिस्तान",
            }
            if any(w in combined for w in ("visit", "meets", "trip", "summit", "tour")):
                for country_en, country_hi in country_map.items():
                    if country_en in combined:
                        return f"#मोदी{country_hi}दौरा"
                return "#मोदीदौरा"
            if any(w in combined for w in ("launch", "inaugurate", "scheme", "project", "yojana")):
                return "#मोदीयोजना"
            return base_tag

        # ── RBI ──────────────────────────────────────────────────────────────
        if keyword == "rbi":
            if any(w in combined for w in ("repo", "rate", "interest", "bps")):
                return "#RBIरेपोरेट"
            if any(w in combined for w in ("digital", "cbdc", "upi")):
                return "#RBIडिजिटल"
            if any(w in combined for w in ("fraud", "scam", "penalty", "fine")):
                return "#RBIबैंकफ्रॉड"
            return "#RBIअपडेट"

        # ── Sensex / Nifty ───────────────────────────────────────────────────
        if keyword in ("sensex", "nifty"):
            label = "सेंसेक्स" if keyword == "sensex" else "निफ्टी"
            if any(w in combined for w in ("fall", "crash", "drop", "down", "slump", "loss")):
                return f"#{label}गिरावट"
            if any(w in combined for w in ("rise", "rally", "surge", "high", "record", "gain")):
                return f"#{label}उछाल"
            return base_tag

        # ── Rupee ─────────────────────────────────────────────────────────────
        if keyword == "rupee":
            if any(w in combined for w in ("fall", "weak", "low", "down", "depreciate")):
                return "#रुपयागिरावट"
            if any(w in combined for w in ("rise", "strong", "high", "gain")):
                return "#रुपयाउछाल"
            return base_tag

        # ── Election ─────────────────────────────────────────────────────────
        if keyword == "election":
            state_map = {
                "bihar": "बिहार", "delhi": "दिल्ली",
                "uttar pradesh": "UP", "maharashtra": "महाराष्ट्र",
                "west bengal": "बंगाल", "bengal": "बंगाल",
                "rajasthan": "राजस्थान", "madhya pradesh": "MP",
                "gujarat": "गुजरात", "karnataka": "कर्नाटक",
                "himachal": "हिमाचल", "uttarakhand": "उत्तराखंड",
                "jharkhand": "झारखंड", "chhattisgarh": "छत्तीसगढ़",
                "goa": "गोवा", "punjab": "पंजाब",
            }
            for state_en, state_hi in state_map.items():
                if state_en in combined:
                    return f"#{state_hi}चुनाव"
            return base_tag

        # ── Protest ──────────────────────────────────────────────────────────
        if keyword == "protest":
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}विरोध"
            proper = _find_proper_noun(sample_titles)
            if proper:
                return f"#{proper}विरोध"
            return base_tag

        # ── Startup ──────────────────────────────────────────────────────────
        if keyword == "startup":
            proper = _find_proper_noun(sample_titles)
            if proper:
                return f"#{proper}स्टार्टअप"
            if "funding" in combined or "raise" in combined or "crore" in combined:
                return "#स्टार्टअपफंडिंग"
            return base_tag

        # ── Army / Defence ────────────────────────────────────────────────────
        if keyword == "army":
            for kw, tag in [("pakistan", "#IndPakसेना"), ("china", "#IndChinaसेना"),
                             ("kashmir", "#कश्मीरसेना"), ("border", "#सीमासेना"),
                             ("strike", "#सर्जिकलस्ट्राइक"), ("airstrike", "#एयरस्ट्राइक")]:
                if kw in combined:
                    return tag
            return base_tag

        # ── Viral / Reel / Meme / Comedy ─────────────────────────────────────
        if keyword in ("viral", "reel", "meme", "comedy"):
            proper = _find_proper_noun(sample_titles)
            if proper:
                suffix = {"meme": "मीम्स", "comedy": "कॉमेडी",
                          "reel": "Reel", "viral": "वायरल"}.get(keyword, "वायरल")
                return f"#{proper}{suffix}"
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}वायरल"
            if "ipl" in combined:
                return "#IPLमीम्स"
            if "bollywood" in combined or "film" in combined or "movie" in combined:
                return "#बॉलीवुडमीम्स"
            return base_tag

        # ── Bhojpuri / Regional ──────────────────────────────────────────────
        if keyword in ("bhojpuri", "haryanvi"):
            proper = _find_proper_noun(sample_titles)
            if proper:
                lang = "भोजपुरी" if keyword == "bhojpuri" else "हरियाणवी"
                return f"#{proper}{lang}"
            if "song" in combined or "gana" in combined or "gaana" in combined:
                return "#भोजपुरीगाना" if keyword == "bhojpuri" else "#हरियाणवीगाना"
            if "film" in combined or "movie" in combined:
                return "#भोजपुरीफिल्म"
            return base_tag

        # ── Festivals (Sawan, Chhath, Teej, etc.) ───────────────────────────
        if keyword in ("sawan", "shravan"):
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}सावन"
            return "#सावनसोमवार"

        if keyword == "chhath":
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}छठपूजा"
            return "#छठपूजा2025"

        if keyword in ("teej", "karva chauth", "vrat"):
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}{base_tag.lstrip('#')}"
            return base_tag

        # ── Ram / Devotional ─────────────────────────────────────────────────
        if keyword == "ram":
            if any(w in combined for w in ("navami", "navmi", "jayanti")):
                return "#रामनवमी"
            if any(w in combined for w in ("mandir", "temple", "ayodhya", "lalla")):
                return "#राममंदिर"
            if any(w in combined for w in ("katha", "bhajan", "kirtan", "bhakt", "pooja", "puja")):
                return "#रामभक्ति"
            return "#रामजन्मभूमि"

        if keyword in ("ayodhya", "ram mandir"):
            if "visit" in combined or "darshan" in combined:
                return "#अयोध्यादर्शन"
            if "inaug" in combined or "open" in combined:
                return "#राममंदिरउद्घाटन"
            return "#राममंदिर"

        if keyword in ("kumbh", "mahakumbh"):
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}कुंभ"
            return "#महाकुंभ2025"

        # ── Exam / Jobs ───────────────────────────────────────────────────────
        if keyword in ("ssc", "upsc"):
            if "result" in combined:
                return f"#{keyword.upper()}Result"
            if "exam" in combined or "paper" in combined:
                return f"#{keyword.upper()}Exam"
            if "vacancy" in combined or "notification" in combined or "form" in combined:
                return f"#{keyword.upper()}Vacancy"
            return base_tag

        if keyword in ("board result", "up board", "bihar board"):
            if "pass" in combined or "merit" in combined or "topper" in combined:
                short = "UPBoard" if "up board" in keyword else "BiharBoard"
                return f"#{short}Topper"
            return base_tag

        if keyword in ("sarkari naukri", "vacancy", "recruitment"):
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}भर्ती"
            proper = _find_proper_noun(sample_titles)
            if proper:
                return f"#{proper}Vacancy"
            return "#सरकारीनौकरी2025"

        if keyword in ("yojana", "scheme"):
            proper = _find_proper_noun(sample_titles)
            if proper:
                return f"#{proper}Yojana"
            return "#सरकारीयोजना"

        # ── Temple ────────────────────────────────────────────────────────────
        if keyword == "temple":
            for city_en, city_hi in CITY_HINDI.items():
                if city_en in combined:
                    return f"#{city_hi}मंदिर"
            proper = _find_proper_noun(sample_titles, min_len=5)
            if proper:
                return f"#{proper}मंदिर"
            if any(w in combined for w in ("dispute", "demolish", "mosque", "masjid")):
                return "#मंदिरविवाद"
            return "#भव्यमंदिर"

        # ── Tier-2 city local topics ──────────────────────────────────────────
        if keyword in ("varanasi", "prayagraj", "kanpur", "lucknow", "gorakhpur",
                       "meerut", "agra", "indore", "bhopal", "patna", "ranchi",
                       "raipur", "jaipur"):
            city_hi = CITY_HINDI.get(keyword, base_tag.lstrip("#"))
            if "rain" in combined or "flood" in combined or "water" in combined:
                return f"#{city_hi}बारिश"
            if "accident" in combined or "road" in combined:
                return f"#{city_hi}हादसा"
            if "crime" in combined or "police" in combined:
                return f"#{city_hi}क्राइम"
            if "heat" in combined or "hot" in combined or "garmi" in combined:
                return f"#{city_hi}गर्मी"
            if "election" in combined or "vote" in combined or "chunav" in combined:
                return f"#{city_hi}चुनाव"
            # Always give city tags context — bare city name is too generic
            return f"#{city_hi}खबर"

    except Exception:
        pass

    return base_tag


# ─── Fallback topics ─────────────────────────────────────────────────────────
# Used when live sources return fewer than 10 results.
# Marked honestly with "fallback" in sources.

FALLBACK_TOPICS = [
    "cricket", "ipl", "bollywood", "bhojpuri",
    "sawan", "viral", "sarkari naukri", "modi",
    "monsoon", "ott", "film", "sensex",
    "varanasi", "chhath", "comedy", "temple",
]


# ─── Helper utilities ────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Strip HTML tags, lowercase, normalize whitespace for keyword matching."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^\w\s\-]", " ", text)
    return text.lower().strip()


def parse_entry_time(entry) -> datetime:
    """Parse RSS entry publish time; fall back to now if missing."""
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)


def hours_ago(dt: datetime) -> float:
    """Return how many hours ago a datetime was."""
    delta = datetime.now(timezone.utc) - dt
    return delta.total_seconds() / 3600


# ─── Stage 1: Fetch Google News RSS ─────────────────────────────────────────

def fetch_google_news() -> list[dict]:
    """
    Pull items from category-specific Google News India RSS feeds.
    Returns: list of {title, published_dt, category_hint, source}
    """
    items = []
    for category, url in GOOGLE_NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:  # top 15 per category
                items.append({
                    "title": entry.get("title", ""),
                    "published_dt": parse_entry_time(entry),
                    "category_hint": category,
                    "source": "Google News",
                })
            logger.info(f"Google News [{category}]: fetched {len(feed.entries)} items")
        except Exception as e:
            logger.warning(f"Google News [{category}] failed — skipping: {e}")
    return items


def fetch_hindi_news() -> list[dict]:
    """
    Pull headlines from verified direct Hindi news RSS sources
    (Amar Ujala, Dainik Bhaskar).  Titles are in Hindi, giving a
    strong Bharat/Tier-2 signal that complements Google News.
    Returns: list of {title, published_dt, category_hint, source}
    """
    items = []
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8",
    }
    for source_name, url in HINDI_DIRECT_FEEDS.items():
        try:
            feed = feedparser.parse(url, request_headers=hdrs)
            count = 0
            for entry in feed.entries[:20]:  # top 20 per source
                title = entry.get("title", "").strip()
                if title:
                    items.append({
                        "title": title,
                        "published_dt": parse_entry_time(entry),
                        "category_hint": "hindi_direct",
                        "source": source_name,
                    })
                    count += 1
            if count:
                logger.info(f"Hindi news [{source_name}]: fetched {count} items")
            else:
                logger.warning(f"Hindi news [{source_name}]: empty feed — skipping")
        except Exception as e:
            logger.warning(f"Hindi news [{source_name}] failed — skipping: {e}")
    return items


# ─── Stage 2: Fetch Google Trends via pytrends ──────────────────────────────

def fetch_google_trends() -> list[str]:
    """
    Attempt to fetch India trending searches via pytrends.
    Returns: list of lowercase trending keyword strings.

    If pytrends is blocked or rate-limited, returns [] and logs a warning.
    The caller should mark search signal as 'estimated' in that case.
    """
    try:
        from pytrends.request import TrendReq  # lazy import — fails gracefully
        pytrends = TrendReq(hl="hi-IN", tz=330, timeout=(5, 20), retries=1)
        df = pytrends.trending_searches(pn="india")
        keywords = [str(k).lower() for k in df[0].tolist()[:20]]
        logger.info(f"Google Trends: fetched {len(keywords)} trending keywords")
        return keywords
    except Exception as e:
        logger.warning(
            f"Google Trends (pytrends) failed — search signal will be estimated. Reason: {e}"
        )
        return []


# ─── Stage 3a: Fetch YouTube Channel RSS ────────────────────────────────────

def fetch_youtube() -> list[dict]:
    """
    Pull recent video titles from major Indian YouTube channels via public RSS.
    No API key required — YouTube exposes channel feeds at:
      https://www.youtube.com/feeds/videos.xml?channel_id=<ID>

    Returns: list of {title, published_dt, source}
    Titles feed into the same keyword-matching pipeline as Reddit items,
    contributing to social_count and the "YouTube" source label.
    """
    items = []
    yt_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    for channel_name, channel_id in YOUTUBE_CHANNELS.items():
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            feed = feedparser.parse(url, request_headers=yt_headers)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                if title:
                    items.append({
                        "title": title,
                        "published_dt": parse_entry_time(entry),
                        "source": "YouTube",
                    })
            if feed.entries:
                logger.info(f"YouTube [{channel_name}]: fetched {len(feed.entries)} videos")
            else:
                logger.warning(f"YouTube [{channel_name}]: empty feed (channel ID may be wrong)")
        except Exception as e:
            logger.warning(f"YouTube [{channel_name}] failed — skipping: {e}")
    return items


# ─── Stage 3b: Fetch Reddit RSS ──────────────────────────────────────────────

def fetch_reddit() -> list[dict]:
    """
    Pull posts from India-relevant subreddits via their public RSS feeds.
    Returns: list of {title, published_dt, source}
    """
    items = []
    for url in REDDIT_FEEDS:
        subreddit = url.split("/r/")[1].rstrip("/.rss")
        try:
            # Reddit RSS sometimes needs a browser-like User-Agent
            feed = feedparser.parse(
                url,
                agent="Mozilla/5.0 (compatible; ShareChatBot/1.0; +https://sharechat.com)"
            )
            for entry in feed.entries[:10]:
                items.append({
                    "title": entry.get("title", ""),
                    "published_dt": parse_entry_time(entry),
                    "source": "Reddit",
                })
            logger.info(f"Reddit [r/{subreddit}]: fetched {len(feed.entries)} items")
        except Exception as e:
            logger.warning(f"Reddit [r/{subreddit}] failed — skipping: {e}")
    return items


# ─── Stage 4: Extract candidate topics ──────────────────────────────────────

def extract_topics(
    news_items: list[dict],
    reddit_items: list[dict],
    trends_keywords: list[str],
    youtube_items: list[dict] | None = None,
) -> dict:
    """
    Scan all titles for known keywords in KEYWORD_TO_TAG.
    Builds topic_data: keyword → {news_count, social_count, search_hit, earliest_dt, sources, sample_titles}

    Why keyword matching?
    - Robust to language differences (Hindi/English headlines both reference same topics)
    - Explainable to a non-engineer audience
    - Fast: O(items × keywords), no ML needed for MVP
    """
    topic_data: dict = defaultdict(lambda: {
        "news_count": 0,
        "social_count": 0,
        "bharat_count": 0,   # hits from Hindi/regional sources (bonus weight in scoring)
        "search_hit": False,
        "earliest_dt": datetime.now(timezone.utc),
        "sources": set(),
        "sample_titles": [],
        "category_hint": None,
    })

    # ── News items (Google News + Hindi direct sources) ──
    _BHARAT_HINTS = {"hi_top", "hi_politics", "hi_sports", "hi_entertain",
                     "hi_tech", "hi_business", "hi_health", "hindi_direct"}
    _BHARAT_SOURCES = {"Amar Ujala", "Dainik Bhaskar"}
    for item in news_items:
        text = clean_text(item["title"])
        item_source = item.get("source", "Google News")
        item_hint   = item.get("category_hint") or ""
        is_bharat   = item_hint in _BHARAT_HINTS or item_source in _BHARAT_SOURCES
        for keyword in KEYWORD_TO_TAG:
            if keyword in text:
                td = topic_data[keyword]
                td["news_count"] += 1
                td["sources"].add(item_source)
                if is_bharat:
                    td["bharat_count"] += 1
                if len(td["sample_titles"]) < 5:
                    td["sample_titles"].append(item["title"][:120])
                if item["published_dt"] < td["earliest_dt"]:
                    td["earliest_dt"] = item["published_dt"]
                if not td["category_hint"]:
                    td["category_hint"] = item_hint or None

    # ── Reddit items ──
    for item in reddit_items:
        text = clean_text(item["title"])
        for keyword in KEYWORD_TO_TAG:
            if keyword in text:
                td = topic_data[keyword]
                td["social_count"] += 1
                td["sources"].add("Reddit")
                if len(td["sample_titles"]) < 5:
                    td["sample_titles"].append(item["title"][:120])
                if item["published_dt"] < td["earliest_dt"]:
                    td["earliest_dt"] = item["published_dt"]

    # ── YouTube items (social/viral signal) ──
    for item in (youtube_items or []):
        text = clean_text(item["title"])
        for keyword in KEYWORD_TO_TAG:
            if keyword in text:
                td = topic_data[keyword]
                td["social_count"] += 1
                td["sources"].add("YouTube")
                if len(td["sample_titles"]) < 5:
                    td["sample_titles"].append(item["title"][:120])
                if item["published_dt"] < td["earliest_dt"]:
                    td["earliest_dt"] = item["published_dt"]

    # ── Google Trends keywords ──
    for trend_kw in trends_keywords:
        for keyword in KEYWORD_TO_TAG:
            if keyword in trend_kw or trend_kw in keyword:
                topic_data[keyword]["search_hit"] = True
                topic_data[keyword]["sources"].add("Google Trends")

    return topic_data


# ─── Stage 5: Compute weighted heat score ───────────────────────────────────

def compute_score(td: dict, trends_available: bool) -> dict:
    """
    Scoring formula (max 100):

      news signal    = min(news_count × 5,   40)   → captures mainstream coverage
      search signal  = 30 if confirmed in Trends    → captures what people search
                       15 if estimated (pytrends failed but news count ≥ 3)
      social signal  = min(social_count × 5, 20)   → captures viral/social buzz
      recency signal = 10 if < 6h | 5 if < 24h | 0 otherwise → freshness bonus

    Why this weighting?
    - News (40): broadest data source, most reliable for India
    - Search (30): gold standard for what's actually top-of-mind
    - Social (20): captures virality not in mainstream news
    - Recency (10): breaks ties in favour of fresh stories
    """
    age_h = hours_ago(td["earliest_dt"])

    # News band: base 4pts per hit (cap 32) + Bharat/Hindi bonus 4pts per hit (cap 8)
    # This prioritises Hindi/regional coverage over generic English news hits.
    news_base    = min(td["news_count"] * 4, 32)
    bharat_bonus = min(td.get("bharat_count", 0) * 4, 8)
    news_score   = news_base + bharat_bonus          # max 40

    social_score  = min(td["social_count"] * 5, 20)
    recency_score = 10 if age_h < 6 else (5 if age_h < 24 else 0)

    if td["search_hit"]:
        search_score = 30
    elif not trends_available and td["news_count"] >= 3:
        # Graceful fallback: if pytrends was blocked, estimate search signal
        # from news frequency — popular topics are usually also searched
        search_score = 15
    else:
        search_score = 0

    return {
        "news":    news_score,
        "search":  search_score,
        "social":  social_score,
        "recency": recency_score,
        "total":   min(news_score + search_score + social_score + recency_score, 100),
    }


# ─── Stage 6: Determine momentum label ──────────────────────────────────────

def get_momentum(td: dict, score: dict) -> str:
    """
    ⚡ Breaking  → very fresh story (< 2 hours old)
    🔥 Rising    → high heat score or mentioned many times
    🟢 New       → default / emerging trend
    """
    age_h = hours_ago(td["earliest_dt"])
    total_mentions = td["news_count"] + td["social_count"]
    if age_h < 2:
        return "⚡ Breaking"
    elif score["total"] >= 60 or total_mentions >= 5:
        return "🔥 Rising"
    else:
        return "🟢 New"


# ─── Stage 7: Why is this trending? ─────────────────────────────────────────

def why_trending(keyword: str, td: dict) -> str:
    sources_str = ", ".join(sorted(td["sources"])) if td["sources"] else "fallback"
    age_h = hours_ago(td["earliest_dt"])
    age_label = f"{int(age_h)}h ago" if age_h < 48 else "today"
    sample = td["sample_titles"][0] if td["sample_titles"] else ""
    headline_note = f' Example headline: "{sample[:90]}…"' if sample else ""
    return (
        f"Spotted across {sources_str} ({age_label}).{headline_note}"
    )


# ─── Category diversity rerank (post heatScore sort) ─────────────────────────
# Light caps + score-band preference — heatScore remains the primary signal.

_DIVERSITY_TOP_N = 10
_DIVERSITY_NEWS_CAP = 3
_DIVERSITY_WEATHER_LOCAL_CAP = 2
_DIVERSITY_SCORE_BAND = 8
_DIVERSITY_MIX_KEYS = frozenset({"sports", "entertainment", "devotional", "viral"})
_WEATHER_LOCAL_KEYS = frozenset({"weather", "local"})


def _pick_diverse_candidate(candidates: list[dict], selected: list[dict]) -> dict:
    """Among similar heatScores, prefer underrepresented mix categories."""
    mix_counts = {k: 0 for k in _DIVERSITY_MIX_KEYS}
    for t in selected:
        ck = t.get("categoryKey")
        if ck in mix_counts:
            mix_counts[ck] += 1

    def priority(t: dict) -> tuple:
        ck = t.get("categoryKey", "")
        if ck in _DIVERSITY_MIX_KEYS:
            return (0, mix_counts[ck], -t["heatScore"])
        if ck in _WEATHER_LOCAL_KEYS:
            wl = sum(1 for s in selected if s.get("categoryKey") in _WEATHER_LOCAL_KEYS)
            return (1, wl, -t["heatScore"])
        return (2, 0, -t["heatScore"])

    return min(candidates, key=priority)


def _find_swap_out_index(selected: list[dict]) -> int:
    """Index of a removable trend to swap for a missing mix category, or -1."""
    news_count = sum(1 for t in selected if t.get("categoryKey") == "news")

    def removable(i: int, t: dict) -> bool:
        ck = t.get("categoryKey")
        if ck in _DIVERSITY_MIX_KEYS:
            if sum(1 for s in selected if s.get("categoryKey") == ck) <= 1:
                return False
        return True

    options = [(i, t) for i, t in enumerate(selected) if removable(i, t)]
    if not options:
        return -1

    news_options = [(i, t) for i, t in options if t.get("categoryKey") == "news" and news_count >= 2]
    pool = news_options if news_options else options
    return min(pool, key=lambda it: it[1]["heatScore"])[0]


def _swap_in_missing_mix(selected: list[dict], pool: list[dict]) -> None:
    """If a mix category is absent, swap one in when its score is close to the cutoff."""
    if len(selected) < _DIVERSITY_TOP_N:
        return

    selected_kw = {t["_keyword"] for t in selected}
    floor = selected[-1]["heatScore"] - _DIVERSITY_SCORE_BAND

    for mix_key in _DIVERSITY_MIX_KEYS:
        if any(t.get("categoryKey") == mix_key for t in selected):
            continue
        candidates = [
            t for t in pool
            if t["_keyword"] not in selected_kw and t.get("categoryKey") == mix_key
        ]
        if not candidates or candidates[0]["heatScore"] < floor:
            continue
        replace_idx = _find_swap_out_index(selected)
        if replace_idx < 0:
            continue
        selected_kw.discard(selected[replace_idx]["_keyword"])
        selected[replace_idx] = candidates[0]
        selected_kw.add(candidates[0]["_keyword"])

    selected.sort(key=lambda x: x["heatScore"], reverse=True)


def _diversify_top_trends(trends: list[dict], size: int = _DIVERSITY_TOP_N) -> list[dict]:
    """
    Select top N trends after heatScore sort with light category diversity.

    Rules:
      - max 3 news/politics (categoryKey == "news")
      - max 2 weather + local combined
      - within an 8-point heatScore band, prefer underrepresented
        sports / entertainment / devotional / viral
    """
    if len(trends) <= size:
        return trends

    pool = list(trends)
    selected: list[dict] = []

    while len(selected) < size and pool:
        news_n = sum(1 for t in selected if t.get("categoryKey") == "news")
        wl_n = sum(1 for t in selected if t.get("categoryKey") in _WEATHER_LOCAL_KEYS)

        eligible = []
        for t in pool:
            ck = t.get("categoryKey", "")
            if ck == "news" and news_n >= _DIVERSITY_NEWS_CAP:
                continue
            if ck in _WEATHER_LOCAL_KEYS and wl_n >= _DIVERSITY_WEATHER_LOCAL_CAP:
                continue
            eligible.append(t)

        if not eligible:
            break

        best_score = eligible[0]["heatScore"]
        close = [t for t in eligible if best_score - t["heatScore"] <= _DIVERSITY_SCORE_BAND]
        pick = _pick_diverse_candidate(close, selected) if len(close) > 1 else eligible[0]

        selected.append(pick)
        pool.remove(pick)

    selected.sort(key=lambda x: x["heatScore"], reverse=True)
    _swap_in_missing_mix(selected, trends)
    return selected


# ─── Build final trend list ──────────────────────────────────────────────────

def build_trends(topic_data: dict, trends_available: bool) -> list[dict]:
    """
    Convert topic_data into ranked, API-ready trend objects.
    Pads to at least 10 using FALLBACK_TOPICS if live sources are sparse.
    """
    trends = []

    for keyword, td in topic_data.items():
        if keyword not in KEYWORD_TO_TAG:
            continue
        tag, category_hi, category_key = KEYWORD_TO_TAG[keyword]
        # Upgrade generic tag to a specific 2-3 word tag using headline context
        tag = sanitize_tag(refine_tag(keyword, tag, td["sample_titles"]))
        score = compute_score(td, trends_available)

        if score["total"] == 0:
            continue

        sources_list = sorted(td["sources"])
        # Mark estimated search signal honestly
        if not trends_available and not td["search_hit"] and td["news_count"] >= 3:
            sources_list = [s for s in sources_list if s != "Google Trends"]
            sources_list.append("Google Trends (estimated)")

        trends.append({
            "_keyword": keyword,
            "tag": tag,
            "title": f"{tag} आज ट्रेंड कर रहा है",
            "description": why_trending(keyword, td),
            "category": category_hi,
            "categoryKey": category_key,
            "heatScore": score["total"],
            "momentum": get_momentum(td, score),
            "sources": sources_list if sources_list else ["Google News (fallback)"],
            "signalBreakdown": {
                "news":    score["news"],
                "search":  score["search"],
                "social":  score["social"],
                "recency": score["recency"],
            },
            "whyTrending": why_trending(keyword, td),
            "postCount": f"{(td['news_count'] + td['social_count'] + 1) * 1400 + 600:,}+",
        })

    # Sort by heat score, then diversify rerank (caps + score-band preference)
    trends.sort(key=lambda x: x["heatScore"], reverse=True)
    trends = _diversify_top_trends(trends)

    # ── Pad to 10 using fallback topics ──────────────────────────────────────
    # This ensures the API always returns ≥10 results, even if sources are dry.
    existing_keywords = {t["_keyword"] for t in trends}
    for fb_kw in FALLBACK_TOPICS:
        if len(trends) >= 10:
            break
        if fb_kw in existing_keywords or fb_kw not in KEYWORD_TO_TAG:
            continue
        tag, category_hi, category_key = KEYWORD_TO_TAG[fb_kw]
        trends.append({
            "_keyword": fb_kw,
            "tag": tag,
            "title": f"{tag} - नियमित ट्रेंड",
            "description": "Regular trending category for Hindi ShareChat users. Live signal unavailable.",
            "category": category_hi,
            "categoryKey": category_key,
            "heatScore": 22,
            "momentum": "🟢 New",
            "sources": ["Google News (fallback)"],
            "signalBreakdown": {"news": 12, "search": 0, "social": 0, "recency": 10},
            "whyTrending": "Baseline category trend based on regular content patterns.",
            "postCount": "1,000+",
        })
        existing_keywords.add(fb_kw)

    # Final sort (fallbacks are at the bottom)
    trends.sort(key=lambda x: x["heatScore"], reverse=True)

    # Assign ranks, strip internal _keyword field
    result = []
    for i, t in enumerate(trends[:10], start=1):
        t.pop("_keyword", None)
        t["rank"] = i
        result.append(t)

    return result


# ─── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    """Instant health check — no pipeline, used by the platform probe."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root():
    """
    Landing page — renders the latest trending tags as a clean HTML table.
    Uses the same live pipeline as /api/trends; refreshes on every page load.
    """
    data = get_trends()

    rows = ""
    for t in data["trends"]:
        sb = t["signalBreakdown"]
        sources_html = "<br>".join(t["sources"])
        rows += f"""
        <tr>
          <td class="rank">{t['rank']}</td>
          <td class="tag">{t['tag']}</td>
          <td class="title-col">{t['title']}</td>
          <td class="desc">{t['description'][:110]}{'…' if len(t['description']) > 110 else ''}</td>
          <td class="cat">{t['category']}<br><small>{t['categoryKey']}</small></td>
          <td class="heat">
            <div class="bar-wrap">
              <div class="score-bar" style="width:{t['heatScore']}%">&nbsp;</div>
              <span class="score-num">{t['heatScore']}</span>
            </div>
          </td>
          <td class="mom">{t['momentum']}</td>
          <td class="src">{sources_html}</td>
          <td class="sig">
            <span title="News (max 40)">📰 {sb['news']}</span>
            <span title="Search (max 30)">🔍 {sb['search']}</span>
            <span title="Social (max 20)">💬 {sb['social']}</span>
            <span title="Recency (max 10)">⏱ {sb['recency']}</span>
          </td>
          <td class="gen">{data['generatedAt'][:19].replace('T', ' ')} UTC</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ShareChat Trending Tags System</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #0a0a0f;
      color: #e0e0e0;
      padding: 2rem 2.5rem;
      font-size: 14px;
      line-height: 1.5;
    }}

    /* ── Header ── */
    header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
      margin-bottom: 1.75rem;
    }}
    .header-left h1 {{
      font-size: 1.65rem;
      font-weight: 700;
      color: #ff6b35;
      letter-spacing: -0.02em;
    }}
    .header-left .subtitle {{
      color: #666;
      font-size: 0.85rem;
      margin-top: 0.3rem;
    }}
    .header-left .subtitle strong {{ color: #999; }}

    /* ── API badge ── */
    .api-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: #1a1a2e;
      border: 1px solid #2a2a4a;
      border-radius: 8px;
      padding: 0.55rem 1rem;
      font-size: 0.82rem;
      color: #999;
      text-decoration: none;
      transition: border-color 0.15s, color 0.15s;
      white-space: nowrap;
    }}
    .api-badge:hover {{ border-color: #ff6b35; color: #ff6b35; }}
    .api-badge code {{
      background: #111;
      color: #ffd700;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.8rem;
      font-family: 'Cascadia Code', 'Fira Code', monospace;
    }}

    /* ── Table wrapper ── */
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
      border-radius: 10px;
      border: 1px solid #1c1c2e;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #111118;
    }}
    thead th {{
      background: #15152a;
      color: #ff6b35;
      padding: 0.75rem 1rem;
      text-align: left;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      white-space: nowrap;
      position: sticky;
      top: 0;
    }}
    tbody td {{
      padding: 0.7rem 1rem;
      border-bottom: 1px solid #18181f;
      vertical-align: top;
    }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr:hover td {{ background: #14142a; }}

    /* ── Cell styles ── */
    .rank {{
      color: #ff6b35;
      font-weight: 700;
      font-size: 1.1rem;
      width: 36px;
      text-align: center;
    }}
    .tag {{
      font-weight: 700;
      font-size: 1rem;
      color: #fff;
      white-space: nowrap;
    }}
    .title-col {{ color: #bbb; max-width: 180px; }}
    .desc {{ color: #777; font-size: 0.8rem; max-width: 240px; line-height: 1.45; }}
    .cat {{ white-space: nowrap; }}
    .cat small {{ color: #555; font-size: 0.72rem; }}

    .bar-wrap {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      min-width: 110px;
    }}
    .score-bar {{
      height: 8px;
      border-radius: 4px;
      background: linear-gradient(90deg, #ff6b35 0%, #ffd700 100%);
      min-width: 3px;
      max-width: 80px;
      flex-shrink: 0;
    }}
    .score-num {{
      font-weight: 700;
      color: #ffd700;
      font-size: 0.9rem;
    }}

    .mom {{ white-space: nowrap; }}
    .src {{ color: #666; font-size: 0.76rem; line-height: 1.7; }}
    .sig span {{
      display: block;
      color: #888;
      font-size: 0.78rem;
      margin-bottom: 1px;
    }}
    .gen {{ color: #444; font-size: 0.72rem; white-space: nowrap; }}

    /* ── Footer ── */
    footer {{
      margin-top: 1.5rem;
      color: #3a3a4a;
      font-size: 0.78rem;
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}
    footer a {{ color: #555; text-decoration: none; }}
    footer a:hover {{ color: #ff6b35; }}
  </style>
</head>
<body>

  <header>
    <div class="header-left">
      <h1>📈 ShareChat Trending Tags System</h1>
      <p class="subtitle">
        Top <strong>{data['count']}</strong> trending tags for
        <strong>{data['audience']}</strong> &nbsp;·&nbsp;
        Generated at <strong>{data['generatedAt'][:19].replace('T', ' ')} UTC</strong>
      </p>
    </div>
    <a class="api-badge" href="/api/trends" target="_blank">
      JSON API &nbsp;→&nbsp; <code>GET /api/trends</code>
    </a>
  </header>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Tag</th>
          <th>Title</th>
          <th>Description</th>
          <th>Category</th>
          <th>Heat Score</th>
          <th>Momentum</th>
          <th>Sources</th>
          <th>Signal Breakdown</th>
          <th>Generated At</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <footer>
    <span>Signal: 📰 News (max 40) · 🔍 Search (max 30) · 💬 Social (max 20) · ⏱ Recency (max 10)</span>
    <span>
      <a href="/api/trends">JSON API</a> &nbsp;·&nbsp;
      <a href="/debug/trends">Debug View</a>
    </span>
  </footer>

</body>
</html>"""

    return HTMLResponse(content=html)


@app.get("/api/trends")
def get_trends():
    """
    Main endpoint: returns top 10 trending tags for Hindi-speaking Indian ShareChat users.

    Pipeline stages (all run fresh on every call — no caching):
      1. Fetch  → Google News RSS, Reddit RSS, Google Trends (pytrends)
      2. Extract → keyword matching across all titles
      3. Score  → weighted heat score
      4. Rank   → top 10 by score
      5. Return → structured JSON with full metadata
    """
    logger.info("=== Trend Pipeline: START ===")

    # Stage 1: Fetch all sources (independent, run sequentially for simplicity)
    news_items      = fetch_google_news()
    hindi_items     = fetch_hindi_news()
    news_items      = news_items + hindi_items      # merge; same schema
    reddit_items    = fetch_reddit()
    youtube_items   = fetch_youtube()
    trends_keywords = fetch_google_trends()

    trends_available = len(trends_keywords) > 0
    logger.info(
        f"Fetched: {len(news_items)} news ({len(hindi_items)} Hindi direct), "
        f"{len(reddit_items)} reddit, {len(youtube_items)} youtube, "
        f"{len(trends_keywords)} trend keywords"
    )

    # Stage 2–7: Extract, score, rank
    topic_data = extract_topics(news_items, reddit_items, trends_keywords, youtube_items)
    trends = build_trends(topic_data, trends_available)

    logger.info(f"=== Trend Pipeline: DONE — {len(trends)} trends ===")

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "audience": "Indian Hindi-speaking users",
        "count": len(trends),
        "trends": trends,
    }


@app.get("/debug/trends", response_class=HTMLResponse)
def debug_trends():
    """
    Debug endpoint: renders current trends as a clean HTML table.
    Designed for demos, PM Loom walkthroughs, and quick sanity checks.
    No auth required — this is a prototype.
    """
    data = get_trends()

    rows = ""
    for t in data["trends"]:
        sb = t["signalBreakdown"]
        sources_html = "<br>".join(t["sources"])
        rows += f"""
        <tr>
          <td class="rank">{t['rank']}</td>
          <td class="tag"><strong>{t['tag']}</strong><br><small>{t['categoryKey']}</small></td>
          <td>{t['category']}</td>
          <td>
            <div class="bar-wrap">
              <div class="score-bar" style="width:{t['heatScore']}%">&nbsp;</div>
              <span class="score-num">{t['heatScore']}</span>
            </div>
          </td>
          <td>{t['momentum']}</td>
          <td class="breakdown">
            <span title="News">📰 {sb['news']}</span>
            <span title="Search">🔍 {sb['search']}</span>
            <span title="Social">💬 {sb['social']}</span>
            <span title="Recency">⏱ {sb['recency']}</span>
          </td>
          <td class="sources">{sources_html}</td>
          <td>{t['postCount']}</td>
          <td class="why">{t['whyTrending'][:100]}{'…' if len(t['whyTrending']) > 100 else ''}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ShareChat Trends — Debug</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0d0d0d; color: #e0e0e0;
      padding: 2rem; font-size: 14px;
    }}
    header {{ margin-bottom: 1.5rem; }}
    h1 {{ color: #ff6b35; font-size: 1.6rem; margin-bottom: 0.3rem; }}
    .meta {{ color: #666; font-size: 0.85rem; }}
    .meta strong {{ color: #999; }}
    table {{
      width: 100%; border-collapse: collapse;
      margin-top: 1rem; background: #111;
      border-radius: 8px; overflow: hidden;
    }}
    th {{
      background: #1a1a2e; color: #ff6b35;
      padding: 0.8rem 1rem; text-align: left;
      font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
    }}
    td {{
      padding: 0.7rem 1rem; border-bottom: 1px solid #1c1c1c;
      vertical-align: middle;
    }}
    tr:hover td {{ background: #161628; }}
    tr:last-child td {{ border-bottom: none; }}
    .rank {{ color: #ff6b35; font-weight: bold; font-size: 1.1rem; width: 40px; }}
    .tag {{ min-width: 130px; }}
    .tag strong {{ font-size: 1rem; }}
    .tag small {{ color: #555; font-size: 0.75rem; }}
    .bar-wrap {{
      display: flex; align-items: center; gap: 0.5rem;
    }}
    .score-bar {{
      height: 10px; border-radius: 5px;
      background: linear-gradient(90deg, #ff6b35 0%, #ffd700 100%);
      min-width: 4px; max-width: 120px;
    }}
    .score-num {{ font-weight: bold; color: #ffd700; }}
    .breakdown span {{
      display: inline-block; margin-right: 0.5rem;
      color: #aaa; font-size: 0.82rem;
    }}
    .sources {{ color: #777; font-size: 0.78rem; line-height: 1.6; }}
    .why {{ color: #888; font-size: 0.78rem; max-width: 280px; line-height: 1.4; }}
    footer {{
      margin-top: 1.5rem; color: #444; font-size: 0.8rem;
    }}
    footer code {{ background: #1a1a1a; padding: 2px 6px; border-radius: 3px; color: #888; }}
  </style>
</head>
<body>
  <header>
    <h1>📈 ShareChat Trending Tags — Debug View</h1>
    <p class="meta">
      Generated: <strong>{data['generatedAt']}</strong> &nbsp;|&nbsp;
      Audience: <strong>{data['audience']}</strong> &nbsp;|&nbsp;
      Count: <strong>{data['count']}</strong>
    </p>
  </header>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Tag</th>
        <th>Category</th>
        <th style="min-width:160px">Heat Score (0–100)</th>
        <th>Momentum</th>
        <th>Signal Breakdown</th>
        <th>Sources</th>
        <th>Est. Posts</th>
        <th>Why Trending</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <footer>
    <p>Signal: 📰 News (max 40) &nbsp;|&nbsp; 🔍 Search (max 30) &nbsp;|&nbsp; 💬 Social (max 20) &nbsp;|&nbsp; ⏱ Recency (max 10)</p>
    <p style="margin-top:0.5rem">
      JSON endpoint: <code>GET /api/trends</code> &nbsp;|&nbsp;
      Refresh this page to re-run the pipeline with fresh data.
    </p>
  </footer>
</body>
</html>"""

    return HTMLResponse(content=html)
