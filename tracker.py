"""
Tracker Module for Duplicate Prevention, Change Detection, and Price History Tracking.
Handles deduplication, state transitions (NEW, UPDATED, UNCHANGED, UNVERIFIED),
and records historical price fluctuations in SQLite.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

import database as db

logger = logging.getLogger("AgriPriceTracker.Tracker")

class TrackingSummary:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.found: int = 0
        self.inserted: int = 0
        self.updated: int = 0
        self.unchanged: int = 0
        self.failed: int = 0
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "found": self.found,
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "failed": self.failed,
            "errors": self.errors
        }


def process_parsed_records(
    valid_records: List[Dict[str, Any]],
    invalid_records: List[Dict[str, Any]],
    run_id: str,
    db_path: Optional[Path] = None
) -> TrackingSummary:
    """
    Core deduplication and change tracking pipeline.
    Compares incoming valid records against existing database state,
    applies price changes, logs audit history, and prevents duplicate records.
    """
    summary = TrackingSummary(run_id=run_id)
    summary.found = len(valid_records) + len(invalid_records)
    summary.failed = len(invalid_records)
    
    for inv in invalid_records:
        err_msg = f"Row {inv.get('row_number', inv.get('index', '?'))}: {', '.join(inv.get('errors', []))}"
        summary.errors.append(err_msg)

    now_iso = datetime.now(timezone.utc).isoformat()

    for record in valid_records:
        source_id = record["source_record_id"]
        existing = db.get_record_by_source_id(source_id, db_path=db_path)

        if existing is None:
            # -------------------------------------------------------------
            # NEW RECORD
            # -------------------------------------------------------------
            record_copy = dict(record)
            record_copy["first_seen"] = now_iso
            record_copy["last_seen"] = now_iso
            record_copy["last_successful_observation"] = now_iso
            record_copy["change_status"] = "NEW"

            new_id = db.insert_price_record(record_copy, db_path=db_path)
            
            # Log initial entry in price_history
            db.add_price_history_entry(
                record_id=new_id,
                source_record_id=source_id,
                run_id=run_id,
                change_type="INITIAL",
                reporting_date=record["reporting_date"],
                observed_at=now_iso,
                prev_min=None,
                new_min=record["min_price"],
                prev_max=None,
                new_max=record["max_price"],
                prev_modal=None,
                new_modal=record["modal_price"],
                details=f"Initial observation of {record['commodity']} at {record['market']} ({record['district']}) on {record['reporting_date']}",
                db_path=db_path
            )
            summary.inserted += 1

        else:
            record_id = existing["id"]
            price_changed = (
                abs(existing["modal_price"] - record["modal_price"]) > 1e-4 or
                abs(existing["min_price"] - record["min_price"]) > 1e-4 or
                abs(existing["max_price"] - record["max_price"]) > 1e-4
            )
            date_changed = (existing["reporting_date"] != record["reporting_date"])

            if price_changed or (date_changed and existing["content_hash"] != record["content_hash"]):
                # ---------------------------------------------------------
                # UPDATED RECORD: Price or bulletin date changed
                # ---------------------------------------------------------
                updates = {
                    "min_price": record["min_price"],
                    "max_price": record["max_price"],
                    "modal_price": record["modal_price"],
                    "reporting_date": record["reporting_date"],
                    "content_hash": record["content_hash"],
                    "last_seen": now_iso,
                    "last_successful_observation": now_iso,
                    "change_status": "UPDATED"
                }
                db.update_price_record(record_id, updates, db_path=db_path)

                # Add historical change entry
                price_delta = record["modal_price"] - existing["modal_price"]
                change_desc = (
                    f"Price shifted by {price_delta:+.2f} {record['price_unit']} (from date {existing['reporting_date']} to {record['reporting_date']}). "
                    f"Modal: {existing['modal_price']} -> {record['modal_price']}, "
                    f"Min: {existing['min_price']} -> {record['min_price']}, "
                    f"Max: {existing['max_price']} -> {record['max_price']}"
                )
                
                db.add_price_history_entry(
                    record_id=record_id,
                    source_record_id=source_id,
                    run_id=run_id,
                    change_type="PRICE_CHANGE",
                    reporting_date=record["reporting_date"],
                    observed_at=now_iso,
                    prev_min=existing["min_price"],
                    new_min=record["min_price"],
                    prev_max=existing["max_price"],
                    new_max=record["max_price"],
                    prev_modal=existing["modal_price"],
                    new_modal=record["modal_price"],
                    details=change_desc,
                    db_path=db_path
                )
                summary.updated += 1

            else:
                # ---------------------------------------------------------
                # UNCHANGED RECORD: Repeated observation without change
                # ---------------------------------------------------------
                updates = {
                    "last_seen": now_iso,
                    "last_successful_observation": now_iso,
                    "change_status": "UNCHANGED"
                }
                db.update_price_record(record_id, updates, db_path=db_path)
                summary.unchanged += 1

    return summary
