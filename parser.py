"""
Parser Module for Agricultural Market Price Extraction and Validation.
Handles HTML table parsing, JSON API payload parsing, and CSV fixture parsing.
Enforces strict schema validation, type conversions, date normalization,
content fingerprint hashing, and error reporting for malformed records.
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("AgriPriceTracker.Parser")

class ParseResult:
    def __init__(self):
        self.valid_records: List[Dict[str, Any]] = []
        self.invalid_records: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.schema_valid: bool = True

    @property
    def total_count(self) -> int:
        return len(self.valid_records) + len(self.invalid_records)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)


def clean_price(val: Any) -> Optional[float]:
    """Cleans currency strings (e.g. '₹ 2,400.00', '2400', ' 3,500 ') to float."""
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "null", "none", "-", "na", "n/a", ""):
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[^\d.]", "", val_str)
    try:
        num = float(cleaned)
        return num if num >= 0 else None
    except ValueError:
        return None


def normalize_date(val: Any) -> Optional[str]:
    """Normalizes various date formats to ISO YYYY-MM-DD string."""
    if not val:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None

    # Common formats in Indian market bulletins
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    # Regex fallback for DD/MM/YYYY
    match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", val_str)
    if match:
        d, m, y = match.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def compute_content_hash(record: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for the price content.
    Used for change detection and duplicate verification.
    """
    keys = ["commodity", "market", "district", "reporting_date", "min_price", "max_price", "modal_price", "price_unit"]
    canonical_str = "|".join(f"{k}:{str(record.get(k, '')).strip().lower()}" for k in keys)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def generate_source_record_id(record: Dict[str, Any]) -> str:
    """Generates a stable unique identifier for a commodity at a market and district."""
    stable_key = f"{record['commodity'].strip().lower()}:{record['market'].strip().lower()}:{record['district'].strip().lower()}:{record['price_unit'].strip().lower()}"
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]


def validate_record_fields(raw: Dict[str, Any], source_url: str = "") -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Validates and standardizes a single raw commodity record dictionary.
    Returns (cleaned_record, list_of_errors).
    """
    errors = []
    
    # 1. Commodity name
    commodity = str(raw.get("commodity") or raw.get("Commodity") or "").strip()
    if not commodity:
        errors.append("Missing required field: commodity")
    else:
        commodity = commodity.title()

    # 2. Market name
    market = str(raw.get("market") or raw.get("Market") or "").strip()
    if not market:
        errors.append("Missing required field: market")
    else:
        market = market.title()

    # 3. District name
    district = str(raw.get("district") or raw.get("District") or "").strip()
    if not district:
        errors.append("Missing required field: district")
    else:
        district = district.title()

    # 4. Reporting Date
    raw_date = raw.get("reporting_date") or raw.get("Arrival_Date") or raw.get("Date") or raw.get("date")
    norm_date = normalize_date(raw_date)
    if not norm_date:
        errors.append(f"Invalid or missing reporting_date: '{raw_date}'")

    # 5. Price fields (min, max, modal)
    min_p = clean_price(raw.get("min_price") or raw.get("Min_x0020_Price") or raw.get("Min Price") or raw.get("min"))
    max_p = clean_price(raw.get("max_price") or raw.get("Max_x0020_Price") or raw.get("Max Price") or raw.get("max"))
    modal_p = clean_price(raw.get("modal_price") or raw.get("Modal_x0020_Price") or raw.get("Modal Price") or raw.get("modal"))

    if min_p is None:
        errors.append("Missing or non-numeric min_price")
    if max_p is None:
        errors.append("Missing or non-numeric max_price")
    if modal_p is None:
        # If modal is missing but min and max exist, fallback to average with warning
        if min_p is not None and max_p is not None:
            modal_p = round((min_p + max_p) / 2.0, 2)
        else:
            errors.append("Missing or non-numeric modal_price")

    # Business rule: max >= min and modal between min and max (with reasonable tolerance)
    if min_p is not None and max_p is not None:
        if max_p < min_p:
            errors.append(f"Price consistency error: max_price ({max_p}) is lower than min_price ({min_p})")
        if modal_p is not None and not (min_p * 0.9 <= modal_p <= max_p * 1.1):
            errors.append(f"Price outlier warning: modal_price ({modal_p}) outside [min, max] range")

    # 6. Price unit (preserve original)
    unit = str(raw.get("price_unit") or raw.get("Price_Unit") or raw.get("Unit") or "Rs/Quintal").strip()
    if not unit:
        unit = "Rs/Quintal"

    if errors:
        return None, errors

    cleaned_record = {
        "commodity": commodity,
        "market": market,
        "district": district,
        "reporting_date": norm_date,
        "min_price": float(min_p),
        "max_price": float(max_p),
        "modal_price": float(modal_p),
        "price_unit": unit,
        "source_url": source_url or raw.get("source_url", "https://agmarknet.gov.in/")
    }

    # Generate stable IDs and content hash
    cleaned_record["source_record_id"] = raw.get("source_record_id") or generate_source_record_id(cleaned_record)
    cleaned_record["content_hash"] = compute_content_hash(cleaned_record)
    
    return cleaned_record, []


def parse_html_table(html_content: str, source_url: str = "https://agmarknet.gov.in/") -> ParseResult:
    """
    Parses HTML table pages (standard AGMARKNET or bulletin structure).
    Extracts headers, validates column mapping, and parses records row-by-row.
    """
    result = ParseResult()
    
    if not html_content or not html_content.strip():
        result.errors.append("Empty HTML payload received")
        result.schema_valid = False
        return result

    soup = BeautifulSoup(html_content, "html.parser")
    
    # Locate table: looking for standard classes or general table
    table = soup.find("table", {"id": re.compile(r"grid|price|market", re.I)}) or soup.find("table", {"class": re.compile(r"table|grid|market", re.I)}) or soup.find("table")
    
    if not table:
        result.errors.append("HTML Schema Failure: No valid data table found matching expected selectors")
        result.schema_valid = False
        return result

    # Extract headers
    rows = table.find_all("tr")
    if not rows:
        result.errors.append("HTML Table has no rows")
        result.schema_valid = False
        return result

    header_cells = rows[0].find_all(["th", "td"])
    headers = [c.get_text(strip=True).lower() for c in header_cells]
    
    # Identify column indexes based on flexible naming
    col_map = {}
    for idx, h in enumerate(headers):
        if any(k in h for k in ["commodity", "item", "vegetable"]):
            col_map["commodity"] = idx
        elif any(k in h for k in ["market", "mandi"]):
            col_map["market"] = idx
        elif any(k in h for k in ["district"]):
            col_map["district"] = idx
        elif any(k in h for k in ["date", "arrival date", "reporting"]):
            col_map["reporting_date"] = idx
        elif any(k in h for k in ["min price", "minimum", "min"]):
            col_map["min_price"] = idx
        elif any(k in h for k in ["max price", "maximum", "max"]):
            col_map["max_price"] = idx
        elif any(k in h for k in ["modal price", "modal"]):
            col_map["modal_price"] = idx
        elif any(k in h for k in ["unit", "price unit"]):
            col_map["price_unit"] = idx

    required_keys = ["commodity", "market", "min_price", "max_price", "modal_price"]
    missing_required = [k for k in required_keys if k not in col_map]
    if missing_required:
        result.errors.append(f"Schema mismatch: missing essential columns {missing_required} in table headers: {headers}")
        result.schema_valid = False
        return result

    # Process data rows
    for row_idx, row in enumerate(rows[1:], start=2):
        cells = row.find_all("td")
        if not cells or len(cells) < len(col_map):
            continue  # Skip divider or malformed rows

        raw_item = {}
        for field, idx in col_map.items():
            if idx < len(cells):
                raw_item[field] = cells[idx].get_text(strip=True)
            else:
                raw_item[field] = None

        # Fallbacks for optional fields
        if "district" not in raw_item or not raw_item["district"]:
            raw_item["district"] = "Tamil Nadu Market"
        if "price_unit" not in raw_item or not raw_item["price_unit"]:
            raw_item["price_unit"] = "Rs/Quintal"

        cleaned, item_errors = validate_record_fields(raw_item, source_url)
        if cleaned:
            result.valid_records.append(cleaned)
        else:
            result.invalid_records.append({"row_number": row_idx, "raw": raw_item, "errors": item_errors})

    return result


def parse_json_records(data: Any, source_url: str = "https://api.data.gov.in/") -> ParseResult:
    """
    Parses Open Government Data (OGD) JSON format.
    Expects records array under 'records' key or root list.
    """
    result = ParseResult()
    
    if not data:
        result.errors.append("Empty JSON data received")
        result.schema_valid = False
        return result

    records_list = []
    if isinstance(data, dict):
        if "records" in data and isinstance(data["records"], list):
            records_list = data["records"]
        else:
            result.errors.append("JSON payload does not contain a 'records' list key")
            result.schema_valid = False
            return result
    elif isinstance(data, list):
        records_list = data
    else:
        result.errors.append("Invalid JSON format: expected list or dict with 'records'")
        result.schema_valid = False
        return result

    for idx, raw in enumerate(records_list):
        cleaned, item_errors = validate_record_fields(raw, source_url)
        if cleaned:
            result.valid_records.append(cleaned)
        else:
            result.invalid_records.append({"index": idx, "raw": raw, "errors": item_errors})

    return result


def parse_csv_content(csv_text: str, source_url: str = "offline://fixtures/csv") -> ParseResult:
    """Parses CSV content representing agricultural price records."""
    import csv
    import io
    result = ParseResult()

    if not csv_text or not csv_text.strip():
        result.errors.append("Empty CSV payload received")
        result.schema_valid = False
        return result

    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        for idx, row in enumerate(reader, start=1):
            cleaned, item_errors = validate_record_fields(row, source_url)
            if cleaned:
                result.valid_records.append(cleaned)
            else:
                result.invalid_records.append({"row_number": idx, "raw": row, "errors": item_errors})
        return result
    except Exception as ex:
        result.errors.append(f"CSV Parsing failure: {ex}")
        result.schema_valid = False
        return result

