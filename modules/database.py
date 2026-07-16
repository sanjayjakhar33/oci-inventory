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
        rows.extend(self._collect_db_systems(compartment_id))
        rows.extend(self._collect_db_homes(compartment_id))
        rows.extend(self._collect_databases(compartment_id))
        rows.extend(self._collect_db_nodes(compartment_id))
        return rows

    def _collect_db_systems(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for db_system in self._paginate(self.manager.database_client.list_db_systems, compartment_id=compartment_id):
            try:
                rows.append(self._build_db_system_row(db_system))
            except Exception as exc:
                logger.exception("Failed to inventory DB system %s: %s", getattr(db_system, "id", "unknown"), exc)
        return rows

    def _collect_db_homes(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for db_home in self._paginate(self.manager.database_client.list_db_homes, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DB Home",
                "Name": getattr(db_home, "display_name", ""),
                "OCID": getattr(db_home, "id", ""),
                "DB System": getattr(db_home, "db_system_id", ""),
                "Lifecycle": getattr(db_home, "lifecycle_state", ""),
            })
        return rows

    def _collect_databases(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for database in self._paginate(self.manager.database_client.list_databases, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Database",
                "Name": getattr(database, "db_name", ""),
                "OCID": getattr(database, "id", ""),
                "DB Home": getattr(database, "db_home_id", ""),
                "Lifecycle": getattr(database, "lifecycle_state", ""),
            })
        return rows

    def _collect_db_nodes(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for db_node in self._paginate(self.manager.database_client.list_db_nodes, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DB Node",
                "Name": getattr(db_node, "hostname", ""),
                "OCID": getattr(db_node, "id", ""),
                "Lifecycle": getattr(db_node, "lifecycle_state", ""),
                "Availability Domain": getattr(db_node, "availability_domain", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            return list(list_call_get_all_results(list_method, **kwargs))
        except Exception as exc:
            logger.warning("Unable to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []

    def _build_db_system_row(self, db_system: Any) -> dict[str, Any]:
        row = {
            "Resource Type": "DB System",
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
