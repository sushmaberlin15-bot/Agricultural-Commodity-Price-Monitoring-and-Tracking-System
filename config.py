"""
Configuration Module for Agricultural Commodity Price Monitoring and Tracking System.
Defines paths, approved commodities, source configurations, scraping safety parameters,
and mentor approval checkpoints.
"""

from pathlib import Path
import os

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "market_prices.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# Source Approval & Operational Mode
# ---------------------------------------------------------
class SourceMode:
    OFFLINE_FIXTURE = "OFFLINE_FIXTURE"
    SYNTHETIC_DEV = "SYNTHETIC_DEV"
    LIVE_API = "LIVE_API"

# Default execution mode: OFFLINE_FIXTURE (Safe, offline-first, compliant)
DEFAULT_SOURCE_MODE = SourceMode.OFFLINE_FIXTURE

# Mentor Live Collection Approval Guard
# Mandatory safeguard: Live automated collection remains locked until explicit mentor verification
MENTOR_LIVE_COLLECTION_APPROVED = False
SOURCE_APPROVAL_BLOCKER_REASON = (
    "Live scraping of government portals (AGMARKNET / Data.gov.in) requires: "
    "1) Formal mentor approval for ethical automated querying; "
    "2) Data.gov.in official API Key registration; "
    "3) Verification of agmarknet.gov.in robots.txt crawl-delay and terms of service; "
    "4) Confirmation that no CAPTCHA or anti-bot mechanism is bypassed. "
    "Use OFFLINE_FIXTURE or SYNTHETIC_DEV mode until these are signed off."
)

# ---------------------------------------------------------
# Candidate Data Sources & Endpoints
# ---------------------------------------------------------
DATA_SOURCES = {
    "AGMARKNET_PORTAL": {
        "name": "Agmarknet Portal (Directorate of Marketing & Inspection)",
        "base_url": "https://agmarknet.gov.in/",
        "daily_prices_url": "https://agmarknet.gov.in/PriceTrends/SA_Pri_Month.aspx",
        "terms_url": "https://agmarknet.gov.in/Terms.aspx",
        "requires_api_key": False,
        "robots_status": "Strict / No automated high-frequency polling allowed",
        "description": "National portal for agricultural marketing data across India."
    },
    "DATA_GOV_IN": {
        "name": "Open Government Data (OGD) Platform India - Agmarknet API",
        "base_url": "https://api.data.gov.in/",
        "resource_endpoint": "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
        "api_key_env_var": "DATAGOVIN_API_KEY",
        "requires_api_key": True,
        "robots_status": "API based with rate limits (10k requests/month with registered key)",
        "description": "Authorized REST API for daily mandi prices under National Data Sharing and Accessibility Policy (NDSAP)."
    },
    "TNAU_AGRITECH": {
        "name": "TNAU Agritech Portal / Uzhavar Sandhai Daily Price Bulletin",
        "base_url": "https://agritech.tnau.ac.in/",
        "description": "Tamil Nadu Agricultural University daily vegetable market bulletin."
    }
}

# ---------------------------------------------------------
# Supported Commodities & Markets (Tamil Nadu)
# ---------------------------------------------------------
CONFIGURED_COMMODITIES = [
    "Tomato",
    "Onion",
    "Potato",
    "Brinjal",
    "Green Chilli",
    "Cabbage",
    "Cauliflower",
    "Drumstick",
    "Carrot",
    "Ladies Finger",
    "Beetroot"
]

CONFIGURED_DISTRICTS = [
    "Chennai",
    "Dindigul",
    "Coimbatore",
    "Madurai",
    "Tiruchirappalli",
    "Salem",
    "Erode",
    "Tirunelveli",
    "Vellore",
    "Thanjavur"
]

CONFIGURED_MARKETS = [
    {"market": "Koyambedu Market", "district": "Chennai"},
    {"market": "Oddanchatram Market", "district": "Dindigul"},
    {"market": "Uzhavar Sandhai R.S. Puram", "district": "Coimbatore"},
    {"market": "Mattuthavani Central Market", "district": "Madurai"},
    {"market": "Gandhi Market", "district": "Tiruchirappalli"},
    {"market": "Shevapet Daily Market", "district": "Salem"},
    {"market": "Nethaji Market", "district": "Erode"},
    {"market": "Palayamkottai Uzhavar Sandhai", "district": "Tirunelveli"}
]

# Standard Price Unit
DEFAULT_PRICE_UNIT = "Rs/Quintal"
ALTERNATIVE_PRICE_UNIT = "Rs/Kg"

# ---------------------------------------------------------
# Network & Scraping Safety Settings
# ---------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0
RATE_LIMIT_DELAY_SECONDS = 1.5
RESPECT_RETRY_AFTER = True

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Compatible AgriPriceTracker/1.0; TN-Research-Project)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ta;q=0.8"
}

# ---------------------------------------------------------
# Scheduler Settings
# ---------------------------------------------------------
DEFAULT_REFRESH_INTERVAL_MINUTES = 60
MIN_REFRESH_INTERVAL_MINUTES = 5
MAX_REFRESH_INTERVAL_MINUTES = 1440

# Stale Data Threshold (hours)
STALE_DATA_THRESHOLD_HOURS = 48
