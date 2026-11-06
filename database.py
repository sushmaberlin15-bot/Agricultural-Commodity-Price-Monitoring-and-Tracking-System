"""
Database Module for SQLite Persistence.
Implements schema creation, transaction management, duplicate prevention,
price history tracking, and query operations for Tamil Nadu agricultural market prices.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from config import DB_PATH

logger = logging.getLogger("AgriPriceTracker.Database")

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Creates and returns a connection to SQLite with row factory and foreign keys enabled."""
    target_path = Path(db_path) if db_path else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes database tables, constraints, and indexes."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Price records table (Current latest state per commodity per market)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_record_id TEXT UNIQUE NOT NULL,
                commodity TEXT NOT NULL,
                market TEXT NOT NULL,
                district TEXT NOT NULL,
                reporting_date TEXT NOT NULL,
                min_price REAL NOT NULL,
                max_price REAL NOT NULL,
                modal_price REAL NOT NULL,
                price_unit TEXT NOT NULL,
                source_url TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_successful_observation TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                change_status TEXT NOT NULL DEFAULT 'NEW',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CONSTRAINT uq_commodity_market UNIQUE(commodity, market, district, price_unit)
            );
        """)
        
        # 2. Price history table (Audit trail of every observation and price change)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                source_record_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                change_type TEXT NOT NULL, -- 'INITIAL', 'PRICE_CHANGE', 'STATUS_CHANGE', 'VERIFIED_UNCHANGED'
                reporting_date TEXT NOT NULL,
                prev_min_price REAL,
                new_min_price REAL,
                prev_max_price REAL,
                new_max_price REAL,
                prev_modal_price REAL,
                new_modal_price REAL,
                observed_at TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (record_id) REFERENCES price_records(id) ON DELETE CASCADE
            );
        """)
        
        # 3. Scrape runs table (Audit trail for data ingestion sessions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                run_id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                finish_time TEXT,
                status TEXT NOT NULL, -- 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'
                source_mode TEXT NOT NULL,
                source_url TEXT,
                records_found INTEGER DEFAULT 0,
                records_inserted INTEGER DEFAULT 0,
                records_updated INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                error_details TEXT
            );
        """)
        
        # Performance Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_commodity_date ON price_records(commodity, reporting_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_district_market ON price_records(district, market);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_content_hash ON price_records(content_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_source_id ON price_history(source_record_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_run_id ON price_history(run_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_reporting_date ON price_history(reporting_date);")
        
        conn.commit()
        logger.info("Database initialized successfully.")

# ---------------------------------------------------------
# Scrape Run Audit Logging
# ---------------------------------------------------------
def log_scrape_start(run_id: str, source_mode: str, source_url: str, db_path: Optional[Path] = None) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO scrape_runs (run_id, start_time, status, source_mode, source_url)
            VALUES (?, ?, 'RUNNING', ?, ?);
        """, (run_id, now_iso, source_mode, source_url))
        conn.commit()

def log_scrape_finish(
    run_id: str,
    status: str,
    records_found: int,
    records_inserted: int,
    records_updated: int,
    records_failed: int,
    error_details: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        conn.execute("""
            UPDATE scrape_runs
            SET finish_time = ?,
                status = ?,
                records_found = ?,
                records_inserted = ?,
                records_updated = ?,
                records_failed = ?,
                error_details = ?
            WHERE run_id = ?;
        """, (now_iso, status, records_found, records_inserted, records_updated, records_failed, error_details, run_id))
        conn.commit()

# ---------------------------------------------------------
# Price Record CRUD & Queries
# ---------------------------------------------------------
def get_record_by_source_id(source_record_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM price_records WHERE source_record_id = ?;", (source_record_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def insert_price_record(record: Dict[str, Any], db_path: Optional[Path] = None) -> int:
    """Inserts a brand-new price record and returns its database id."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO price_records (
                source_record_id, commodity, market, district, reporting_date,
                min_price, max_price, modal_price, price_unit, source_url,
                first_seen, last_seen, last_successful_observation,
                content_hash, change_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            record["source_record_id"],
            record["commodity"],
            record["market"],
            record["district"],
            record["reporting_date"],
            float(record["min_price"]),
            float(record["max_price"]),
            float(record["modal_price"]),
            record["price_unit"],
            record["source_url"],
            record.get("first_seen", now_iso),
            record.get("last_seen", now_iso),
            record.get("last_successful_observation", now_iso),
            record["content_hash"],
            record.get("change_status", "NEW"),
            now_iso,
            now_iso
        ))
        conn.commit()
        return cursor.lastrowid

def update_price_record(
    record_id: int,
    updates: Dict[str, Any],
    db_path: Optional[Path] = None
) -> None:
    """Updates fields of an existing price record."""
    now_iso = datetime.now(timezone.utc).isoformat()
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    fields.append("updated_at = ?")
    values.append(now_iso)
    values.append(record_id)
    
    query = f"UPDATE price_records SET {', '.join(fields)} WHERE id = ?;"
    with get_connection(db_path) as conn:
        conn.execute(query, tuple(values))
        conn.commit()

def add_price_history_entry(
    record_id: int,
    source_record_id: str,
    run_id: str,
    change_type: str,
    reporting_date: str,
    observed_at: str,
    prev_min: Optional[float] = None,
    new_min: Optional[float] = None,
    prev_max: Optional[float] = None,
    new_max: Optional[float] = None,
    prev_modal: Optional[float] = None,
    new_modal: Optional[float] = None,
    details: Optional[str] = None,
    db_path: Optional[Path] = None
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO price_history (
                record_id, source_record_id, run_id, change_type, reporting_date,
                prev_min_price, new_min_price, prev_max_price, new_max_price,
                prev_modal_price, new_modal_price, observed_at, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            record_id, source_record_id, run_id, change_type, reporting_date,
            prev_min, new_min, prev_max, new_max, prev_modal, new_modal,
            observed_at, details
        ))
        conn.commit()
        return cursor.lastrowid

# ---------------------------------------------------------
# Reporting & Dashboard Queries
# ---------------------------------------------------------
def get_all_records(
    commodity: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieves filtered price records sorted by reporting_date DESC."""
    query = "SELECT * FROM price_records WHERE 1=1"
    params = []
    
    if commodity and commodity != "All":
        query += " AND commodity = ?"
        params.append(commodity)
    if district and district != "All":
        query += " AND district = ?"
        params.append(district)
    if market and market != "All":
        query += " AND market = ?"
        params.append(market)
    if start_date:
        query += " AND reporting_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND reporting_date <= ?"
        params.append(end_date)
        
    query += " ORDER BY reporting_date DESC, commodity ASC, market ASC;"
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]

def get_summary_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Retrieves high-level overview metrics for KPIs."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) AS total FROM price_records;")
        total_records = cursor.fetchone()["total"]
        
        cursor.execute("SELECT COUNT(DISTINCT market) AS markets FROM price_records;")
        total_markets = cursor.fetchone()["markets"]
        
        cursor.execute("SELECT COUNT(DISTINCT commodity) AS commodities FROM price_records;")
        total_commodities = cursor.fetchone()["commodities"]
        
        cursor.execute("SELECT COUNT(DISTINCT district) AS districts FROM price_records;")
        total_districts = cursor.fetchone()["districts"]
        
        cursor.execute("SELECT COUNT(*) AS new_count FROM price_records WHERE change_status = 'NEW';")
        new_count = cursor.fetchone()["new_count"]
        
        cursor.execute("SELECT COUNT(*) AS updated_count FROM price_records WHERE change_status = 'UPDATED';")
        updated_count = cursor.fetchone()["updated_count"]

        cursor.execute("SELECT COUNT(*) AS unchanged_count FROM price_records WHERE change_status = 'UNCHANGED';")
        unchanged_count = cursor.fetchone()["unchanged_count"]
        
        cursor.execute("""
            SELECT * FROM scrape_runs 
            WHERE status = 'SUCCESS' 
            ORDER BY finish_time DESC LIMIT 1;
        """)
        last_success_run = cursor.fetchone()
        
        cursor.execute("""
            SELECT * FROM scrape_runs 
            ORDER BY start_time DESC LIMIT 1;
        """)
        latest_run = cursor.fetchone()
        
        return {
            "total_records": total_records,
            "total_markets": total_markets,
            "total_commodities": total_commodities,
            "total_districts": total_districts,
            "new_count": new_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "last_success_run": dict(last_success_run) if last_success_run else None,
            "latest_run": dict(latest_run) if latest_run else None
        }

def get_scrape_runs(limit: int = 50, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM scrape_runs 
            ORDER BY start_time DESC LIMIT ?;
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def get_price_history(
    source_record_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    query = """
        SELECT h.*, r.commodity, r.market, r.district, r.price_unit
        FROM price_history h
        JOIN price_records r ON h.record_id = r.id
    """
    params = []
    if source_record_id:
        query += " WHERE h.source_record_id = ?"
        params.append(source_record_id)
        
    query += " ORDER BY h.observed_at DESC, h.reporting_date DESC LIMIT ?;"
    params.append(limit)
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]

def get_historical_trends(
    commodity: str,
    district: Optional[str] = None,
    market: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieves chronologically sorted observations from price_history for Plotly trend charting."""
    query = """
        SELECT r.commodity, r.market, r.district, r.price_unit,
               h.reporting_date, h.new_min_price AS min_price,
               h.new_max_price AS max_price, h.new_modal_price AS modal_price,
               h.observed_at
        FROM price_history h
        JOIN price_records r ON h.record_id = r.id
        WHERE r.commodity = ?
    """
    params = [commodity]
    if district and district != "All":
        query += " AND r.district = ?"
        params.append(district)
    if market and market != "All":
        query += " AND r.market = ?"
        params.append(market)
        
    query += " ORDER BY h.reporting_date ASC, h.observed_at ASC;"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        
        # If no history entries yet, fallback to price_records table
        if not rows:
            cursor.execute("""
                SELECT commodity, market, district, price_unit, reporting_date,
                       min_price, max_price, modal_price, last_seen AS observed_at
                FROM price_records
                WHERE commodity = ?
                ORDER BY reporting_date ASC;
            """, (commodity,))
            rows = [dict(r) for r in cursor.fetchall()]
            
        return rows
