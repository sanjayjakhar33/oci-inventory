"""Database inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache, to_iso_string

logger = logging.getLogger(__name__)


class DatabaseCollector:
    """Collect OCI database system inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for db_system in self._list_db_systems(compartment_id):
            try:
                rows.append(self._build_db_system_row(db_system))
            except Exception as exc:
                logger.exception("Failed to inventory DB system %s: %s", getattr(db_system, "id", "unknown"), exc)
        return rows

    def _list_db_systems(self, compartment_id: str) -> list[Any]:
        try:
            return list(list_call_get_all_results(self.manager.database_client.list_db_systems, compartment_id=compartment_id))
        except Exception as exc:
            logger.warning("Unable to list DB systems in compartment %s: %s", compartment_id, exc)
            return []

    def _build_db_system_row(self, db_system: Any) -> dict[str, Any]:
        row = {
            "DB System": getattr(db_system, "display_name", ""),
            "DB System OCID": getattr(db_system, "id", ""),
            "Database Name": "",
            "Version": getattr(db_system, "database_software_image", "") or "",
            "Shape": getattr(db_system, "shape", ""),
            "Lifecycle": getattr(db_system, "lifecycle_state", ""),
            "Private IP": "",
            "Public IP": "",
            "Subnet": "",
            "VCN": "",
            "NSGs": "",
        }

        try:
            endpoint = self.manager.database_client.get_db_system(db_system_id=getattr(db_system, "id", "")).data
            row["Private IP"] = getattr(endpoint, "hostname", "")
        except Exception as exc:
            logger.warning("Unable to get DB system details for %s: %s", getattr(db_system, "id", ""), exc)

        if getattr(db_system, "subnet_id", None):
            subnet = self.cache.get_subnet(getattr(db_system, "subnet_id", ""))
            if subnet is None:
                try:
                    subnet = self.manager.virtual_network_client.get_subnet(subnet_id=getattr(db_system, "subnet_id", "")).data
                    self.cache.cache_subnet(getattr(db_system, "subnet_id", ""), subnet)
                except Exception as exc:
                    logger.warning("Unable to get subnet for DB system %s: %s", getattr(db_system, "id", ""), exc)
            if subnet is not None:
                row["Subnet"] = getattr(subnet, "display_name", "")
                vcn = self.cache.get_vcn(getattr(subnet, "vcn_id", ""))
                if vcn is None:
                    try:
                        vcn = self.manager.virtual_network_client.get_vcn(vcn_id=getattr(subnet, "vcn_id", "")).data
                        self.cache.cache_vcn(getattr(subnet, "vcn_id", ""), vcn)
                    except Exception as exc:
                        logger.warning("Unable to get VCN for DB system %s: %s", getattr(db_system, "id", ""), exc)
                if vcn is not None:
                    row["VCN"] = getattr(vcn, "display_name", "")

        return row
