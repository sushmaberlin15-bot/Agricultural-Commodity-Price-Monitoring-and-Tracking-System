# Agricultural Commodity Price Monitoring and Tracking System
### Tamil Nadu Vegetable Markets (Agmarknet & OGD Platform Standards)

A full-stack agricultural commodity price tracking, change detection, and analytics web application built with **Python**, **Streamlit**, **Plotly**, and **SQLite**.

Designed specifically for farmers, traders, agricultural researchers, and students to monitor vegetable prices across key Tamil Nadu mandis and Uzhavar Sandhais (e.g., Koyambedu Chennai, Oddanchatram Dindigul, Uzhavar Sandhai R.S. Puram Coimbatore, Mattuthavani Madurai, Gandhi Market Tiruchirappalli, Shevapet Salem).

---

## 1. Project Architecture

The application adopts a modular, decoupled architecture:

```
major project 1/
├── app.py                  # Streamlit analytics dashboard and interactive UI
├── scraper.py              # Configurable source adapters (Offline, Synthetic, Live API)
├── parser.py               # Extraction, cleaning, date normalization, schema validation
├── database.py             # SQLite persistence, indexing, transactional audit logging
├── tracker.py              # Deduplication engine, state transitions (NEW/UPDATED/UNCHANGED)
├── scheduler.py            # Thread-safe background periodic collection & manual triggers
├── config.py               # Commodities list, mandis, timeouts, rate limits, mentor guard
├── data/
│   ├── market_prices.db    # SQLite relational database
│   └── fixtures/           # Authorized offline HTML and CSV snapshots (Cycles 1, 2, 3, Challenge)
│       ├── fixture_run_1.html      # Baseline snapshot (34+ valid records)
│       ├── fixture_run_2.html      # Cycle 2 refresh (price shifts & new commodities)
│       ├── fixture_run_3.html      # Cycle 3 refresh (further updates + isolated malformed test rows)
│       ├── fixture_challenge.html  # Altered DOM selector challenge
│       └── fixture_tn_agri.csv     # Alternative authorized CSV format
├── logs/                   # System runtime logs and audit entries
├── tests/
│   ├── test_parser.py      # Field validation, cleaning, error handling, CSV/HTML parsing
│   ├── test_database.py    # Schema constraints, indexing, CRUD, scrape run audit
│   ├── test_tracker.py     # Deduplication, price delta calculation, status transitions
│   └── test_scraper.py     # 3-cycle refresh tracking, mentor guardrail, challenge handling
├── requirements.txt        # Python package dependencies
├── .gitignore              # Clean repository management
└── README.md               # Complete architecture, setup, testing, and SRS documentation
```

---

## 2. Key Capabilities & Technical Highlights

- **Configurable Source Adapters (`scraper.py`):**
  - **`OfflineFixtureAdapter`:** High-fidelity offline development mode using realistic Tamil Nadu market price bulletins. Works with zero internet dependency.
  - **`SyntheticDevAdapter`:** Realistic synthetic simulation mode with controlled price drift for long-term stress testing.
  - **`LiveAgmarknetAdapter`:** Guarded live scraper adhering to strict ethical protocols: exponential backoff, rate limiting delays (1.5s), timeout limits (15s), and HTTP 429/Retry-After respect.
- **Strict Mentor Approval Guardrail:**
  Live automated scraping is locked behind `config.MENTOR_LIVE_COLLECTION_APPROVED = False`. Attempting unauthorized automated requests immediately triggers `SourceApprovalRequiredError` to protect public infrastructure and comply with institutional guidelines.
- **Deduplication & Content Fingerprinting (`tracker.py`):**
  - Generates deterministic **SHA-256 content hashes** across all price dimensions.
  - Unique composite key constraint `(commodity, market, district, price_unit)` prevents duplicate records on repeated ingestion runs.
- **Price History & Change Audit (`database.py`):**
  - Changes are recorded in `price_history` with previous vs new prices and human-readable transition descriptions.
  - Non-destructive failure isolation: Malformed rows or failed runs never delete or corrupt existing price records.
- **Professional Analytics Dashboard (`app.py`):**
  - **Overview & KPIs:** Total records, monitored mandis, freshness indicators (< 48 hrs status), and run audit logs.
  - **Vegetable Market Prices Explorer:** Multi-criteria filtering by commodity, district, market, and date range with CSV export.
  - **Inter-Market Price Comparison:** Grouped visual bar charts comparing Min, Max, and Modal prices, complete with an **Economic & Trader Advisory Note** on transport, grading, and commission costs.
  - **Historical Price Trends:** Interactive Plotly line charts displaying time-series price movements across reporting dates.
  - **Change Tracker:** Real-time audit trail of state transitions (`NEW`, `UPDATED`, `UNCHANGED`).
  - **Collection & Controller:** One-click manual triggers for Cycle 1 (Baseline), Cycle 2 (Updates), Cycle 3 (Malformed Row Isolation), and Synthetic Simulation.
  - **Source Approval Matrix:** Detailed Cybernaut SRS checklist and mentor compliance matrix.

---

## 3. Technology Stack

| Component | Library / Tool | Purpose |
| :--- | :--- | :--- |
| Backend & Logic | Python 3.10+ (Tested on 3.14) | Core application programming language |
| Web Scraping | `requests`, `beautifulsoup4` | Permitted HTTP communication & DOM extraction |
| Data Processing | `pandas` | Tabular data transformations and CSV exports |
| Storage | `sqlite3` | Relational database with foreign keys & indexes |
| Web Dashboard | `streamlit` | Responsive agricultural web UI |
| Visualizations | `plotly` | Interactive time-series line & grouped bar charts |
| Testing Suite | `pytest` | 21 comprehensive automated unit and integration tests |

---

## 4. Setup & Installation Instructions

### Prerequisites
- Python 3.10 or higher installed.
- PowerShell or Terminal.

### Step 1: Open Terminal in Project Directory
```powershell
cd "c:\Users\Gopika S\Downloads\major project 1"
```

### Step 2: Create and Activate Virtual Environment (Optional but Recommended)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

---

## 5. Running the Application

Launch the Streamlit interactive dashboard:
```powershell
python -m streamlit run app.py
```
Once started, open your web browser at:
```
http://localhost:8501
```

---

## 6. Running the Automated Test Suite

Run the full pytest suite (all 21 automated tests):
```powershell
python -m pytest -v
```

### Test Coverage Summary:
- **`tests/test_parser.py`:**
  - Price cleaning (currency symbols, commas, whitespace, invalid tokens).
  - Date normalization (YYYY-MM-DD, DD/MM/YYYY, DD-Mon-YYYY).
  - SHA-256 deterministic fingerprinting.
  - Min/Max/Modal price consistency validation (rejects inverted prices).
  - Required field presence (commodity, market, date).
  - HTML table selector parsing and changed DOM selector detection.
  - Authorized CSV fixture parsing.
- **`tests/test_database.py`:**
  - Database schema initialization with foreign keys.
  - Insertion and retrieval of price records.
  - Unique composite key duplicate rejection.
  - Scrape run logging (`RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`).
- **`tests/test_tracker.py`:**
  - Initial run: all items marked `NEW`, `price_history` populated with `INITIAL`.
  - Repeat run: 0 records inserted, items marked `UNCHANGED`, zero duplication.
  - Price change run: updates detected, items marked `UPDATED`, price deltas recorded.
  - Malformed record isolation: bad rows logged without corrupting valid data.
- **`tests/test_scraper.py`:**
  - Offline fixture ingestion of Cycle 1 baseline (34+ valid records).
  - Multi-cycle execution (Cycle 1 -> Cycle 2 updates -> Cycle 3 malformed row handling).
  - Mentor live collection guard: verifies `SourceApprovalRequiredError` is raised.
  - Mentor DOM challenge fixture: handles altered layout gracefully.

---

## 7. Data Source Approval & Ethical Scraping Guidelines

### Candidate Sources Evaluated:
1. **AGMARKNET Portal (`https://agmarknet.gov.in/`):**
   - *Status:* Directorate of Marketing & Inspection (DMI), Ministry of Agriculture.
   - *Robots Guidance & Terms:* Disallows aggressive or high-frequency polling. Uses ASP.NET ViewState controls.
   - *Ethical Action:* Direct automated scraping is kept **disabled** by default.
2. **Open Government Data (OGD) Platform India (`https://api.data.gov.in/`):**
   - *Status:* Official national data portal published under National Data Sharing and Accessibility Policy (NDSAP).
   - *Resource:* Daily Mandi Price API Resource (`9ef84268-d588-465a-a308-a864a43d0070`).
   - *Authorized Method:* REST API requiring user registration and API key with generous monthly rate limits.
3. **TNAU Agritech Portal (`https://agritech.tnau.ac.in/`):**
   - *Status:* Tamil Nadu Agricultural University daily market bulletins for local Uzhavar Sandhais.

### Mentor Checkpoint Status (Cybernaut SRS Matrix):
| Checkpoint | SRS Requirement | Implementation & Verification Status |
| :--- | :--- | :--- |
| **CP-1** | Source alternatives and written approval | **Documented in `config.py` & `README.md`**. Data.gov.in API established as primary lawful source. |
| **CP-2** | Prototype with 10 reviewed records & dictionary | **Completed**. 34+ authentic records across 8 key Tamil Nadu markets configured. |
| **CP-3** | Validated, deduplicated, repeatable DB pipeline | **Completed & Tested**. Deduplication verified via unit tests; 0 duplicates on reruns. |
| **CP-4** | Three refresh cycles with visible changes | **Completed & Tested**. Cycle 1 (Baseline), Cycle 2 (Updates), Cycle 3 (Malformed Error Isolation). |
| **CP-5** | Mentor challenge: malformed rows & altered schema | **Completed**. `fixture_run_3.html` and `fixture_challenge.html` handle bad data safely. |
| **CP-6** | Source ethics, request limits, Git governance | **Completed**. Exponential backoff, timeout limits, and explicit mentor approval guardrail. |

### How to Enable Live API Collection (Pending Mentor Sign-off):
1. Register for an official API key at [data.gov.in](https://www.data.gov.in/).
2. Set the environment variable:
   ```powershell
   $env:DATAGOVIN_API_KEY="your_api_key_here"
   ```
3. In `config.py`, toggle:
   ```python
   MENTOR_LIVE_COLLECTION_APPROVED = True
   ```

---

## 8. Multi-Cycle Demonstration Guide

To demonstrate the full lifecycle during a project review or mentor inspection:

1. **Start the Dashboard:**
   ```powershell
   python -m streamlit run app.py
   ```
2. **Navigate to "📋 Data Collection & Runs":**
   - Click **"▶️ Run Cycle 1 (Baseline)"**: Observes 34 records discovered and inserted with status `NEW`.
   - Click **"▶️ Run Cycle 2 (Updates)"**: Observes price fluctuations (Tomato rises by ₹300/Q, Onion drops by ₹200/Q) and 2 new commodities added.
   - Click **"▶️ Run Cycle 3 (Malformed Test)"**: Demonstrates fault tolerance. 3 corrupted test rows (inverted price, corrupt string, empty name) are caught and logged as `PARTIAL` without terminating the process or damaging valid records.
3. **Navigate to "📈 Historical Price Trends":**
   - Select **Tomato** or **Onion** to view the Plotly line chart rendering real price shifts across the recorded dates.
4. **Navigate to "🔄 Change Tracker & Audit":**
   - Review the detailed previous vs new price deltas and transition timestamps.
5. **Navigate to "⚖️ Market Price Comparison":**
   - Compare mandi spreads between Koyambedu (Chennai), Oddanchatram (Dindigul), R.S. Puram (Coimbatore), and Gandhi Market (Tiruchirappalli).

---

## 9. Known Limitations & Next Steps

1. **Live Network Ingestion Guard:** Live scraping of `agmarknet.gov.in` remains deliberately disabled until mentor verification and formal Data.gov.in API key registration.
2. **Future Enhancements:**
   - Multi-language UI support (Tamil language localization for local farmers).
   - SMS/WhatsApp price alert notifications via Twilio or Gupshup for local Uzhavar Sandhai arrivals.
   - Machine Learning price forecasting model (ARIMA/Prophet) utilizing the stored historical observations.
