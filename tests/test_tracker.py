"""
Unit Tests for Tracker Module.
Verifies deduplication, state transitions (NEW, UNCHANGED, UPDATED),
price history creation, and resilience against failures.
"""

import pytest
from pathlib import Path
import database as db
import tracker

@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_tracker.db"
    db.init_db(db_path=db_file)
    return db_file

def make_test_record(commodity="Tomato", modal=2800.0, date="2026-10-18"):
    return {
        "source_record_id": f"{commodity.lower()}_koyambedu",
        "commodity": commodity,
        "market": "Koyambedu Market",
        "district": "Chennai",
        "reporting_date": date,
        "min_price": modal - 300,
        "max_price": modal + 300,
        "modal_price": modal,
        "price_unit": "Rs/Quintal",
        "source_url": "https://agmarknet.gov.in/",
        "content_hash": f"hash_{commodity}_{modal}_{date}"
    }

def test_initial_run_inserts_records_and_history(temp_db):
    rec = make_test_record("Tomato", 2800.0)
    summary = tracker.process_parsed_records(
        valid_records=[rec],
        invalid_records=[],
        run_id="RUN_INITIAL",
        db_path=temp_db
    )
    assert summary.inserted == 1
    assert summary.updated == 0
    assert summary.unchanged == 0

    # Verify record in DB
    saved = db.get_record_by_source_id(rec["source_record_id"], db_path=temp_db)
    assert saved is not None
    assert saved["change_status"] == "NEW"

    # Verify price history
    history = db.get_price_history(rec["source_record_id"], db_path=temp_db)
    assert len(history) == 1
    assert history[0]["change_type"] == "INITIAL"
    assert history[0]["new_modal_price"] == 2800.0

def test_repeated_run_does_not_duplicate(temp_db):
    rec = make_test_record("Tomato", 2800.0)
    
    # Run 1
    tracker.process_parsed_records([rec], [], "RUN_1", db_path=temp_db)

    # Run 2 with IDENTICAL data
    summary2 = tracker.process_parsed_records([rec], [], "RUN_2", db_path=temp_db)
    assert summary2.inserted == 0
    assert summary2.updated == 0
    assert summary2.unchanged == 1

    # Ensure total records in DB is still exactly 1
    records = db.get_all_records(db_path=temp_db)
    assert len(records) == 1
    assert records[0]["change_status"] == "UNCHANGED"

def test_price_change_updates_and_creates_history(temp_db):
    rec1 = make_test_record("Tomato", 2800.0)
    tracker.process_parsed_records([rec1], [], "RUN_1", db_path=temp_db)

    # Price increases to 3200
    rec2 = make_test_record("Tomato", 3200.0)
    summary2 = tracker.process_parsed_records([rec2], [], "RUN_2", db_path=temp_db)
    assert summary2.inserted == 0
    assert summary2.updated == 1
    assert summary2.unchanged == 0

    # Ensure price in DB is updated
    updated = db.get_record_by_source_id(rec1["source_record_id"], db_path=temp_db)
    assert updated["modal_price"] == 3200.0
    assert updated["change_status"] == "UPDATED"

    # Verify history has 2 entries (INITIAL and PRICE_CHANGE)
    history = db.get_price_history(rec1["source_record_id"], db_path=temp_db)
    assert len(history) == 2
    assert history[0]["change_type"] == "PRICE_CHANGE"
    assert history[0]["prev_modal_price"] == 2800.0
    assert history[0]["new_modal_price"] == 3200.0

def test_failed_and_malformed_records_isolated(temp_db):
    valid_rec = make_test_record("Potato", 2200.0)
    invalid_rec = {
        "index": 1,
        "raw": {"commodity": "CorruptItem"},
        "errors": ["Inconsistent price values: min > max"]
    }
    
    summary = tracker.process_parsed_records(
        valid_records=[valid_rec],
        invalid_records=[invalid_rec],
        run_id="RUN_MALFORMED",
        db_path=temp_db
    )
    assert summary.inserted == 1
    assert summary.failed == 1
    assert len(summary.errors) == 1
    assert "Inconsistent price values" in summary.errors[0]
