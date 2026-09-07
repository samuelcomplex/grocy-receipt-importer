import os
from pathlib import Path


GROCY_BASE_URL = os.environ.get("GROCY_BASE_URL", "http://grocy").rstrip("/")
GROCY_API_KEY = os.environ.get("GROCY_API_KEY", "")

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "receipts.sqlite3")

TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"
DEFAULT_LANGUAGE = "en"


RECEIPT_STORAGE = os.environ.get("RECEIPT_STORAGE", "sqlite").lower()
MAPPING_STORAGE = os.environ.get("MAPPING_STORAGE", "sqlite").lower()
