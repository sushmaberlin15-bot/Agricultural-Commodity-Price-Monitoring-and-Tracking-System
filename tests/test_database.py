"""
Unit Tests for Database Module.
Tests SQLite schema creation, insertion, queries, duplicate constraints,
history tracking, and run audit logs using an isolated in-memory or temporary database.
"""

import pytest
import sqlite3
from pathlib import Path
import database as db

@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_market_prices.db"
    db.init_db(db_path=db_file)
    return db_file

def test_init_db_creates_tables(temp_db):
    with db.get_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "price_records" in tables
        assert "price_history" in tables
        assert "scrape_runs" in tables

def test_insert_and_retrieve_record(temp_db):
    sample = {
        "source_record_id": "rec_001",
        "commodity": "Tomato",
        "market": "Koyambedu Market",
        "district": "Chennai",
        "reporting_date": "2026-10-18",
        "min_price": 2500.0,
        "max_price": 3100.0,
        "modal_price": 2800.0,
        "price_unit": "Rs/Quintal",
        "source_url": "https://agmarknet.gov.in/",
        "content_hash": "hash123",
        "change_status": "NEW"
    }
    rec_id = db.insert_price_record(sample, db_path=temp_db)
    assert rec_id > 0

    fetched = db.get_record_by_source_id("rec_001", db_path=temp_db)
    assert fetched is not None
    assert fetched["commodity"] == "Tomato"
    assert fetched["modal_price"] == 2800.0
    assert fetched["change_status"] == "NEW"

def test_duplicate_source_id_rejected(temp_db):
    sample = {
        "source_record_id": "rec_unique",
        "commodity": "Onion",
        "market": "Oddanchatram Market",
        "district": "Dindigul",
        "reporting_date": "2026-10-18",
        "min_price": 2800.0,
        "max_price": 3400.0,
        "modal_price": 3100.0,
        "price_unit": "Rs/Quintal",
        "source_url": "https://agmarknet.gov.in/",
        "content_hash": "hash_onion",
        "change_status": "NEW"
    }
    db.insert_price_record(sample, db_path=temp_db)

    # Attempting to insert duplicate source_record_id should raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_price_record(sample, db_path=temp_db)

def test_scrape_run_logging(temp_db):
    run_id = "RUN_TEST_001"
    db.log_scrape_start(run_id, "OFFLINE_FIXTURE", "offline://test", db_path=temp_db)
    
    db.log_scrape_finish(
        run_id=run_id,
        status="SUCCESS",
        records_found=10,
        records_inserted=8,
        records_updated=2,
        records_failed=0,
        db_path=temp_db
    )

    runs = db.get_scrape_runs(db_path=temp_db)
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "SUCCESS"
    assert runs[0]["records_inserted"] == 8
