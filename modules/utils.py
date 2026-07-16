"""Shared utility helpers for OCI inventory collection."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import LOG_FILE, SETTINGS


def setup_logging(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """Configure logging to a file and the console."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(Path(log_dir) / "oci_inventory.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)


def setup_logger() -> logging.Logger:
    """Compatibility wrapper for the repository's older logging entrypoint."""
    return setup_logging()


def get_signer() -> tuple[dict[str, str], None]:
    """Compatibility shim for CLI-profile based execution.

    The inventory generator must use the OCI CLI config profile rather than
    resource principals, so this shim simply returns the active region config.
    """
    return {"region": SETTINGS.get("region", "us-ashburn-1")}, None


def sanitize_sheet_name(name: str) -> str:
    """Trim sheet names to the supported workbook limit."""
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in (" ", "_", "-"))
    return cleaned[:31] or "Sheet"


def safe_value(value: Any) -> Any:
    """Normalize values that may not be JSON serializable for the workbook."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


def to_iso_string(value: Any) -> str:
    """Convert OCI timestamps to a stable iso string."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


class InventoryCache:
    """In-memory caches used to avoid repeated OCI lookups for related resources."""

    def __init__(self) -> None:
        self.vcns: dict[str, dict[str, Any]] = {}
        self.subnets: dict[str, dict[str, Any]] = {}
        self.nsgs: dict[str, dict[str, Any]] = {}
        self.route_tables: dict[str, dict[str, Any]] = {}
        self.security_lists: dict[str, dict[str, Any]] = {}
        self.dhcp_options: dict[str, dict[str, Any]] = {}
        self.cpes: dict[str, dict[str, Any]] = {}

    def cache_vcn(self, vcn_id: str, payload: dict[str, Any]) -> None:
        if vcn_id:
            self.vcns[vcn_id] = payload

    def get_vcn(self, vcn_id: str) -> dict[str, Any] | None:
        return self.vcns.get(vcn_id)

    def cache_subnet(self, subnet_id: str, payload: dict[str, Any]) -> None:
        if subnet_id:
            self.subnets[subnet_id] = payload

    def get_subnet(self, subnet_id: str) -> dict[str, Any] | None:
        return self.subnets.get(subnet_id)

    def cache_nsg(self, nsg_id: str, payload: dict[str, Any]) -> None:
        if nsg_id:
            self.nsgs[nsg_id] = payload

    def get_nsg(self, nsg_id: str) -> dict[str, Any] | None:
        return self.nsgs.get(nsg_id)

    def cache_route_table(self, route_table_id: str, payload: dict[str, Any]) -> None:
        if route_table_id:
            self.route_tables[route_table_id] = payload

    def get_route_table(self, route_table_id: str) -> dict[str, Any] | None:
        return self.route_tables.get(route_table_id)

    def cache_security_list(self, security_list_id: str, payload: dict[str, Any]) -> None:
        if security_list_id:
            self.security_lists[security_list_id] = payload

    def get_security_list(self, security_list_id: str) -> dict[str, Any] | None:
        return self.security_lists.get(security_list_id)

    def cache_dhcp_options(self, dhcp_options_id: str, payload: dict[str, Any]) -> None:
        if dhcp_options_id:
            self.dhcp_options[dhcp_options_id] = payload

    def get_dhcp_options(self, dhcp_options_id: str) -> dict[str, Any] | None:
        return self.dhcp_options.get(dhcp_options_id)

    def cache_cpe(self, cpe_id: str, payload: dict[str, Any]) -> None:
        if cpe_id:
            self.cpes[cpe_id] = payload

    def get_cpe(self, cpe_id: str) -> dict[str, Any] | None:
        return self.cpes.get(cpe_id)


def normalize_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Return a small, workbook-friendly resource dictionary."""
    return {key: safe_value(value) for key, value in resource.items()}


def join_values(values: list[Any] | tuple[Any, ...] | set[Any]) -> str:
    """Join values consistently for workbook cells."""
    return ", ".join(str(value) for value in values if value not in (None, ""))
