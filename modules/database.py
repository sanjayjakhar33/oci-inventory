"""Database inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class DatabaseCollector:
    """Collect OCI database system inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        """Collect database inventory following the OCI hierarchy:
        Compartment -> DB Systems -> DB Homes -> Databases -> DB Nodes
        """
        rows: list[dict[str, Any]] = []
        
        # Collect DB Systems and related hierarchy
        db_systems = self._list_db_systems(compartment_id)
        for db_system in db_systems:
            try:
                rows.append(self._build_db_system_row(db_system))
            except Exception as exc:
                logger.exception("Failed to inventory DB system %s: %s", getattr(db_system, "id", "unknown"), exc)
            
            db_system_id = getattr(db_system, "id", "")
            if db_system_id:
                # Collect DB Homes for this DB System
                try:
                    db_homes = self._list_db_homes(db_system_id)
                    for db_home in db_homes:
                        try:
                            rows.append(self._build_db_home_row(db_home))
                        except Exception as exc:
                            logger.warning("Failed to inventory DB home %s: %s", getattr(db_home, "id", "unknown"), exc)
                        
                        db_home_id = getattr(db_home, "id", "")
                        if db_home_id:
                            # Collect Databases for this DB Home
                            try:
                                databases = self._list_databases(db_home_id)
                                for database in databases:
                                    try:
                                        rows.append(self._build_database_row(database, db_home))
                                    except Exception as exc:
                                        logger.warning("Failed to inventory database %s: %s", getattr(database, "id", "unknown"), exc)
                            except Exception as exc:
                                logger.warning("Failed to list databases for DB home %s: %s", db_home_id, exc)
                except Exception as exc:
                    logger.warning("Failed to list DB homes for DB system %s: %s", db_system_id, exc)
                
                # Collect DB Nodes for this DB System
                try:
                    db_nodes = self._list_db_nodes(db_system_id)
                    for db_node in db_nodes:
                        try:
                            rows.append(self._build_db_node_row(db_node))
                        except Exception as exc:
                            logger.warning("Failed to inventory DB node %s: %s", getattr(db_node, "id", "unknown"), exc)
                except Exception as exc:
                    logger.warning("Failed to list DB nodes for DB system %s: %s", db_system_id, exc)
        
        return rows

    def _list_db_systems(self, compartment_id: str) -> list[Any]:
        """List all DB Systems in a compartment."""
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_db_systems,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Unable to list DB systems in compartment %s: %s", compartment_id, exc)
            return []

    def _list_db_homes(self, db_system_id: str) -> list[Any]:
        """List all DB Homes in a DB System."""
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_db_homes,
                db_system_id=db_system_id,
            )
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Unable to list DB homes for DB system %s: %s", db_system_id, exc)
            return []

    def _list_databases(self, db_home_id: str) -> list[Any]:
        """List all Databases in a DB Home."""
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_databases,
                db_home_id=db_home_id,
            )
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Unable to list databases for DB home %s: %s", db_home_id, exc)
            return []

    def _list_db_nodes(self, db_system_id: str) -> list[Any]:
        """List all DB Nodes in a DB System."""
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_db_nodes,
                db_system_id=db_system_id,
            )
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Unable to list DB nodes for DB system %s: %s", db_system_id, exc)
            return []


    def _build_db_home_row(self, db_home: Any) -> dict[str, Any]:
        """Build a row for a DB Home resource."""
        return {
            "Resource Type": "DB Home",
            "Name": getattr(db_home, "display_name", ""),
            "OCID": getattr(db_home, "id", ""),
            "DB System": getattr(db_home, "db_system_id", ""),
            "Version": getattr(db_home, "db_version", ""),
            "Lifecycle": getattr(db_home, "lifecycle_state", ""),
        }

    def _build_database_row(self, database: Any, db_home: Any) -> dict[str, Any]:
        """Build a row for a Database resource."""
        return {
            "Resource Type": "Database",
            "Name": getattr(database, "db_name", ""),
            "OCID": getattr(database, "id", ""),
            "DB Home": getattr(database, "db_home_id", ""),
            "DB Home Name": getattr(db_home, "display_name", ""),
            "Admin User": getattr(database, "admin_user_name", ""),
            "Lifecycle": getattr(database, "lifecycle_state", ""),
            "Character Set": getattr(database, "character_set", ""),
            "NCHAR Character Set": getattr(database, "ncharacter_set", ""),
        }

    def _build_db_node_row(self, db_node: Any) -> dict[str, Any]:
        """Build a row for a DB Node resource."""
        return {
            "Resource Type": "DB Node",
            "Name": getattr(db_node, "hostname", ""),
            "OCID": getattr(db_node, "id", ""),
            "DB System": getattr(db_node, "db_system_id", ""),
            "Lifecycle": getattr(db_node, "lifecycle_state", ""),
            "Availability Domain": getattr(db_node, "availability_domain", ""),
            "Fault Domain": getattr(db_node, "fault_domain", ""),
        }

    def _build_db_system_row(self, db_system: Any) -> dict[str, Any]:
        """Build a row for a DB System resource."""
        row = {
            "Resource Type": "DB System",
            "Name": getattr(db_system, "display_name", ""),
            "OCID": getattr(db_system, "id", ""),
            "Database Edition": getattr(db_system, "database_edition", ""),
            "Version": getattr(db_system, "database_software_image", "") or "",
            "Shape": getattr(db_system, "shape", ""),
            "Lifecycle": getattr(db_system, "lifecycle_state", ""),
            "CPU Core Count": getattr(db_system, "cpu_core_count", ""),
            "Storage Size GB": getattr(db_system, "storage_size_in_gbs", ""),
            "Private IP": "",
            "Subnet": "",
            "VCN": "",
            "NSGs": "",
            "Availability Domain": getattr(db_system, "availability_domain", ""),
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
