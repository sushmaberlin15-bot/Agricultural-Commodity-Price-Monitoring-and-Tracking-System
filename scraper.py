"""
Scraper Module with Configurable Source Adapters.
Implements ethical data collection architecture:
- Offline Fixture Adapter (authorized offline development datasets)
- Synthetic Development Adapter (controlled testing & simulation)
- Live Agmarknet / OGD Adapter (strict mentor approval guard, backoff, rate limits)
"""

import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests

import config
import database as db
import parser
import tracker

logger = logging.getLogger("AgriPriceTracker.Scraper")

class SourceApprovalRequiredError(Exception):
    """Raised when live automated collection is attempted without mentor verification."""
    pass

class ScraperRateLimitError(Exception):
    """Raised when server responds with HTTP 429 Too Many Requests."""
    pass

class ScraperNetworkError(Exception):
    """Raised on network connection failures or non-recoverable HTTP errors."""
    pass


class BaseSourceAdapter:
    """Abstract base adapter for agricultural commodity price collection."""
    
    def __init__(self, source_mode: str, source_url: str):
        self.source_mode = source_mode
        self.source_url = source_url

    def fetch(self) -> str:
        raise NotImplementedError

    def parse(self, raw_content: str) -> parser.ParseResult:
        raise NotImplementedError

    def run_pipeline(self, db_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Executes an end-to-end collection, parsing, deduplication, and persistence run.
        Ensures audit logging in scrape_runs table.
        """
        run_id = f"RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        logger.info(f"Starting collection run {run_id} via {self.source_mode}")
        
        db.log_scrape_start(run_id, self.source_mode, self.source_url, db_path=db_path)
        
        try:
            raw_content = self.fetch()
            parse_res = self.parse(raw_content)
            
            # Execute deduplication and change tracking
            tracking_res = tracker.process_parsed_records(
                valid_records=parse_res.valid_records,
                invalid_records=parse_res.invalid_records,
                run_id=run_id,
                db_path=db_path
            )
            
            # Determine run status
            if parse_res.errors and not parse_res.valid_records:
                status = "FAILED"
                err_text = "; ".join(parse_res.errors)
            elif parse_res.invalid_records or parse_res.errors:
                status = "PARTIAL"
                err_text = f"Parsed {parse_res.valid_count} valid, {parse_res.invalid_count} rejected. Errors: {'; '.join(parse_res.errors + [e for inv in parse_res.invalid_records for e in inv.get('errors', [])])}"
            else:
                status = "SUCCESS"
                err_text = None
                
            db.log_scrape_finish(
                run_id=run_id,
                status=status,
                records_found=tracking_res.found,
                records_inserted=tracking_res.inserted,
                records_updated=tracking_res.updated,
                records_failed=tracking_res.failed,
                error_details=err_text,
                db_path=db_path
            )
            
            return {
                "run_id": run_id,
                "status": status,
                "source_mode": self.source_mode,
                "records_found": tracking_res.found,
                "records_inserted": tracking_res.inserted,
                "records_updated": tracking_res.updated,
                "records_unchanged": tracking_res.unchanged,
                "records_failed": tracking_res.failed,
                "errors": parse_res.errors + tracking_res.errors
            }
            
        except Exception as ex:
            logger.error(f"Run {run_id} encountered fatal error: {str(ex)}", exc_info=True)
            db.log_scrape_finish(
                run_id=run_id,
                status="FAILED",
                records_found=0,
                records_inserted=0,
                records_updated=0,
                records_failed=0,
                error_details=str(ex),
                db_path=db_path
            )
            return {
                "run_id": run_id,
                "status": "FAILED",
                "source_mode": self.source_mode,
                "records_found": 0,
                "records_inserted": 0,
                "records_updated": 0,
                "records_unchanged": 0,
                "records_failed": 0,
                "errors": [str(ex)]
            }


class OfflineFixtureAdapter(BaseSourceAdapter):
    """
    Authorized Offline Fixture Adapter.
    Uses pre-captured Tamil Nadu agricultural market bulletins.
    Provides repeatable, offline-first verification across snapshots.
    """
    
    def __init__(self, cycle: int = 1, fixture_file: Optional[str] = None):
        self.cycle = cycle
        filename = fixture_file or f"fixture_run_{cycle}.html"
        self.file_path = config.FIXTURES_DIR / filename
        super().__init__(
            source_mode=config.SourceMode.OFFLINE_FIXTURE,
            source_url=f"offline://fixtures/{filename}"
        )

    def fetch(self) -> str:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {self.file_path}")
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    def parse(self, raw_content: str) -> parser.ParseResult:
        if self.file_path.suffix.lower() == ".csv":
            return parser.parse_csv_content(raw_content, source_url=self.source_url)
        return parser.parse_html_table(raw_content, source_url=self.source_url)


class SyntheticDevAdapter(BaseSourceAdapter):
    """
    Synthetic Development Adapter.
    Simulates live daily market bulletins for Tamil Nadu with configurable drift.
    Clearly marked to prevent mistaking test data for live feeds.
    """
    
    def __init__(self, date_str: Optional[str] = None, price_drift_pct: float = 0.0):
        super().__init__(
            source_mode=config.SourceMode.SYNTHETIC_DEV,
            source_url="synthetic://tamilnadu.vegetables.dev"
        )
        self.date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.price_drift_pct = price_drift_pct

    def fetch(self) -> str:
        # Generate realistic dataset
        import random
        # Base realistic prices (Rs/Quintal) in Tamil Nadu markets
        base_prices = {
            "Tomato": (2500, 3200, 2800),
            "Onion": (2900, 3600, 3200),
            "Potato": (2200, 2800, 2500),
            "Brinjal": (1700, 2300, 2000),
            "Green Chilli": (3800, 4600, 4200),
            "Cabbage": (1200, 1700, 1450),
            "Cauliflower": (2100, 2700, 2400),
            "Drumstick": (3300, 4200, 3700),
            "Carrot": (3100, 3900, 3500),
            "Ladies Finger": (1900, 2500, 2200)
        }
        
        rows_html = []
        for m in config.CONFIGURED_MARKETS:
            for comm in config.CONFIGURED_COMMODITIES[:7]:
                min_p, max_p, modal_p = base_prices.get(comm, (2000, 2600, 2300))
                # Apply drift
                factor = 1.0 + self.price_drift_pct + random.uniform(-0.04, 0.04)
                adj_min = int(min_p * factor)
                adj_max = int(max_p * factor)
                adj_modal = int(modal_p * factor)
                rows_html.append(f"""
                    <tr>
                        <td>{m['district']}</td>
                        <td>{m['market']}</td>
                        <td>{comm}</td>
                        <td>{self.date_str}</td>
                        <td>{adj_min}</td>
                        <td>{adj_max}</td>
                        <td>{adj_modal}</td>
                        <td>Rs/Quintal</td>
                    </tr>
                """)
                
        return f"""
        <html>
            <body>
                <table id="cphBody_GridPriceData">
                    <thead>
                        <tr>
                            <th>District</th>
                            <th>Market</th>
                            <th>Commodity</th>
                            <th>Reporting Date</th>
                            <th>Min Price</th>
                            <th>Max Price</th>
                            <th>Modal Price</th>
                            <th>Unit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </body>
        </html>
        """

    def parse(self, raw_content: str) -> parser.ParseResult:
        return parser.parse_html_table(raw_content, source_url=self.source_url)


class LiveAgmarknetAdapter(BaseSourceAdapter):
    """
    Live Network Adapter for Agmarknet / OGD Platform.
    Enforces ethical scraping guidelines, exponential backoff, rate limiting,
    and requires mentor authorization before any network requests are dispatched.
    """
    
    def __init__(self, target_url: Optional[str] = None):
        super().__init__(
            source_mode=config.SourceMode.LIVE_API,
            source_url=target_url or config.DATA_SOURCES["AGMARKNET_PORTAL"]["daily_prices_url"]
        )

    def fetch(self) -> str:
        # Mandatory Ethical Checkpoint
        if not config.MENTOR_LIVE_COLLECTION_APPROVED:
            raise SourceApprovalRequiredError(
                f"Live automated collection BLOCKED. {config.SOURCE_APPROVAL_BLOCKER_REASON}"
            )
            
        logger.info(f"Connecting to live endpoint: {self.source_url} with rate-limiting...")
        retries = config.MAX_RETRIES
        delay = config.RATE_LIMIT_DELAY_SECONDS
        
        session = requests.Session()
        session.headers.update(config.HTTP_HEADERS)
        
        for attempt in range(1, retries + 1):
            try:
                time.sleep(delay)
                response = session.get(self.source_url, timeout=config.REQUEST_TIMEOUT_SECONDS)
                
                # Respect HTTP 429 & Retry-After
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))
                    logger.warning(f"Rate limited (HTTP 429). Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                if response.status_code in (401, 403):
                    raise ScraperNetworkError(f"Access forbidden (HTTP {response.status_code}). Portal anti-bot or authorization required.")

                response.raise_for_status()
                return response.text

            except requests.Timeout:
                logger.warning(f"Attempt {attempt}/{retries} timed out after {config.REQUEST_TIMEOUT_SECONDS}s.")
                if attempt == retries:
                    raise ScraperNetworkError("Request timed out across all retries.")
            except requests.RequestException as req_err:
                logger.warning(f"Attempt {attempt}/{retries} failed: {req_err}")
                if attempt == retries:
                    raise ScraperNetworkError(f"HTTP connection failed: {req_err}")

            delay *= config.BACKOFF_FACTOR

        raise ScraperNetworkError("Max retries exceeded without successful response.")

    def parse(self, raw_content: str) -> parser.ParseResult:
        return parser.parse_html_table(raw_content, source_url=self.source_url)


def get_adapter(mode: str = config.DEFAULT_SOURCE_MODE, **kwargs) -> BaseSourceAdapter:
    """Factory function returning the appropriate source adapter."""
    if mode == config.SourceMode.OFFLINE_FIXTURE:
        cycle = kwargs.get("cycle", 1)
        fixture_file = kwargs.get("fixture_file")
        return OfflineFixtureAdapter(cycle=cycle, fixture_file=fixture_file)
    elif mode == config.SourceMode.SYNTHETIC_DEV:
        return SyntheticDevAdapter(
            date_str=kwargs.get("date_str"),
            price_drift_pct=kwargs.get("price_drift_pct", 0.0)
        )
    elif mode == config.SourceMode.LIVE_API:
        return LiveAgmarknetAdapter(target_url=kwargs.get("target_url"))
    else:
        raise ValueError(f"Unknown source mode: {mode}")
