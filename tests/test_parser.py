"""
Unit Tests for Parser Module.
Validates extraction, data cleaning, type conversions, content hashing,
and malformed row handling.
"""

import pytest
import parser

def test_clean_price():
    assert parser.clean_price("2500") == 2500.0
    assert parser.clean_price("₹ 2,400.50") == 2400.50
    assert parser.clean_price("  3,100  ") == 3100.0
    assert parser.clean_price("-") is None
    assert parser.clean_price("N/A") is None
    assert parser.clean_price("INVALID") is None
    assert parser.clean_price("") is None
    assert parser.clean_price(None) is None

def test_normalize_date():
    assert parser.normalize_date("2026-10-18") == "2026-10-18"
    assert parser.normalize_date("18/10/2026") == "2026-10-18"
    assert parser.normalize_date("18-10-2026") == "2026-10-18"
    assert parser.normalize_date("18-Oct-2026") == "2026-10-18"
    assert parser.normalize_date("invalid-date") is None

def test_compute_content_hash_deterministic():
    rec1 = {
        "commodity": "Tomato",
        "market": "Koyambedu Market",
        "district": "Chennai",
        "reporting_date": "2026-10-18",
        "min_price": 2600.0,
        "max_price": 3200.0,
        "modal_price": 2900.0,
        "price_unit": "Rs/Quintal"
    }
    rec2 = dict(rec1)
    # Identical content yields identical hash
    assert parser.compute_content_hash(rec1) == parser.compute_content_hash(rec2)

    # Different price yields different hash
    rec3 = dict(rec1, modal_price=3100.0)
    assert parser.compute_content_hash(rec1) != parser.compute_content_hash(rec3)

def test_validate_record_fields_valid():
    raw = {
        "commodity": "tomato",
        "market": "koyambedu market",
        "district": "chennai",
        "reporting_date": "18/10/2026",
        "min_price": "2,400",
        "max_price": "3,000",
        "modal_price": "2,700",
        "price_unit": "Rs/Quintal"
    }
    cleaned, errors = parser.validate_record_fields(raw)
    assert errors == []
    assert cleaned is not None
    assert cleaned["commodity"] == "Tomato"
    assert cleaned["market"] == "Koyambedu Market"
    assert cleaned["reporting_date"] == "2026-10-18"
    assert cleaned["min_price"] == 2400.0
    assert cleaned["max_price"] == 3000.0
    assert cleaned["modal_price"] == 2700.0
    assert cleaned["price_unit"] == "Rs/Quintal"

def test_validate_record_fields_inconsistent_prices():
    # Min price > Max price
    raw = {
        "commodity": "Tomato",
        "market": "Koyambedu",
        "district": "Chennai",
        "reporting_date": "2026-10-18",
        "min_price": "3500",
        "max_price": "2500",
        "modal_price": "3000"
    }
    cleaned, errors = parser.validate_record_fields(raw)
    assert cleaned is None
    assert any("Price consistency error" in e for e in errors)

def test_validate_record_fields_missing_commodity():
    raw = {
        "commodity": "",
        "market": "Koyambedu",
        "district": "Chennai",
        "reporting_date": "2026-10-18",
        "min_price": "2500",
        "max_price": "3000",
        "modal_price": "2800"
    }
    cleaned, errors = parser.validate_record_fields(raw)
    assert cleaned is None
    assert any("Missing required field: commodity" in e for e in errors)

def test_parse_html_table_success():
    sample_html = """
    <table>
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
        <tr>
            <td>Chennai</td>
            <td>Koyambedu</td>
            <td>Tomato</td>
            <td>18/10/2026</td>
            <td>2500</td>
            <td>3000</td>
            <td>2800</td>
            <td>Rs/Quintal</td>
        </tr>
    </table>
    """
    res = parser.parse_html_table(sample_html)
    assert res.schema_valid is True
    assert res.valid_count == 1
    assert res.invalid_count == 0
    record = res.valid_records[0]
    assert record["commodity"] == "Tomato"
    assert record["min_price"] == 2500.0

def test_parse_html_table_changed_schema():
    bad_html = "<div><p>No table present in this mentor challenge page</p></div>"
    res = parser.parse_html_table(bad_html)
    assert res.schema_valid is False
    assert res.valid_count == 0
    assert len(res.errors) > 0

def test_parse_csv_content():
    csv_text = """District,Market,Commodity,Arrival_Date,Min Price,Max Price,Modal Price,Unit
Chennai,Koyambedu Market,Tomato,2026-10-18,2600,3200,2900,Rs/Quintal
Dindigul,Oddanchatram Market,Onion,2026-10-18,2800,3400,3100,Rs/Quintal
"""
    res = parser.parse_csv_content(csv_text)
    assert res.schema_valid is True
    assert res.valid_count == 2
    assert res.invalid_count == 0
    assert res.valid_records[0]["commodity"] == "Tomato"
    assert res.valid_records[1]["commodity"] == "Onion"

