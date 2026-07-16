import os
from dotenv import load_dotenv

load_dotenv()

SETTINGS = {
    "profile": os.getenv("OCI_PROFILE", "DEFAULT"),
    "region": os.getenv("OCI_REGION", "us-ashburn-1"),
    "config_file": os.getenv("OCI_CONFIG_FILE", "~/.oci/config"),
}
