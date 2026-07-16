from pathlib import Path

BASE_DIR = Path(__file__).parent

OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "OCI_Inventory.xlsx"
LOG_FILE = LOG_DIR / "inventory.log"
