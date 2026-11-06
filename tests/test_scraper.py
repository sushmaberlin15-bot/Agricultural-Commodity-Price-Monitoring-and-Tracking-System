"""
Integration Tests for Scraper Adapters.
Tests offline fixture runs, multi-cycle refresh tracking,
mentor approval guardrails, and challenge schema handling.
"""

import pytest
from pathlib import Path
import config
import database as db
import scraper

@pytest.fixture
def temp_db(tmp_path: Path):
    db_file = tmp_path / "test_scraper_integration.db"
    db.init_db(db_path=db_file)
    return db_file

def test_offline_fixture_cycle_1_initial(temp_db):
    adapter = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=1)
    res = adapter.run_pipeline(db_path=temp_db)
    
    assert res["status"] == "SUCCESS"
    assert res["records_inserted"] >= 30
    assert res["records_updated"] == 0
    assert res["records_failed"] == 0

    stats = db.get_summary_stats(db_path=temp_db)
    assert stats["total_records"] >= 30
    assert stats["new_count"] >= 30

def test_offline_three_refresh_cycles(temp_db):
    # Cycle 1: Baseline
    ad1 = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=1)
    res1 = ad1.run_pipeline(db_path=temp_db)
    assert res1["status"] == "SUCCESS"
    initial_count = res1["records_inserted"]
    assert initial_count >= 30

    # Cycle 2: Updates and additions
    ad2 = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=2)
    res2 = ad2.run_pipeline(db_path=temp_db)
    assert res2["status"] == "SUCCESS"
    assert res2["records_updated"] > 0
    assert res2["records_inserted"] > 0  # e.g., Garlic added

    # Cycle 3: Further updates and intentional malformed test records
    ad3 = scraper.get_adapter(config.SourceMode.OFFLINE_FIXTURE, cycle=3)
    res3 = ad3.run_pipeline(db_path=temp_db)
    assert res3["status"] == "PARTIAL"  # Malformed records isolated
    assert res3["records_failed"] == 3
    assert res3["records_updated"] > 0

    # Verify history audit entries exist for updated records
    runs = db.get_scrape_runs(db_path=temp_db)
    assert len(runs) == 3
    history = db.get_price_history(limit=50, db_path=temp_db)
    assert len(history) > initial_count

def test_live_scraper_blocked_without_approval():
    # Ensure config flag is False
    config.MENTOR_LIVE_COLLECTION_APPROVED = False
    live_adapter = scraper.get_adapter(config.SourceMode.LIVE_API)
    
    with pytest.raises(scraper.SourceApprovalRequiredError) as exc_info:
        live_adapter.fetch()
    assert "Live automated collection BLOCKED" in str(exc_info.value)

def test_challenge_fixture_selector_failure(temp_db):
    challenge_adapter = scraper.get_adapter(
        config.SourceMode.OFFLINE_FIXTURE,
        fixture_file="fixture_challenge.html"
    )
    res = challenge_adapter.run_pipeline(db_path=temp_db)
    assert res["status"] == "FAILED"
    assert any("HTML Schema Failure" in err for err in res["errors"])
