"""Application configuration for the OCI inventory generator."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

for directory in (OUTPUT_DIR, LOG_DIR):
    if directory.exists() and not directory.is_dir():
        directory.unlink()
    directory.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "OCI_Inventory.xlsx"
LOG_FILE = LOG_DIR / "inventory.log"

SETTINGS = {
    "profile": os.getenv("OCI_PROFILE", "DEFAULT"),
    "region": os.getenv("OCI_REGION", "us-ashburn-1"),
    "config_file": os.getenv("OCI_CONFIG_FILE", str(Path.home() / ".oci" / "config")),
}
