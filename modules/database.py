"""Database inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class DatabaseCollector:
    """Collect OCI database system inventory for a compartment.

    The collector inventories DB Systems, DB Homes, Databases, DB Nodes,
    Autonomous Databases, Cloud VM Clusters and Cloud Exadata Infrastructures
    for the target compartment. Network metadata (private IP, subnet, VCN)
    is enriched using the shared InventoryCache.
    """

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        # DB Systems (co-managed / BM / VM / Exadata legacy)
        db_systems = self._list_db_systems(compartment_id)
        db_system_ids = {getattr(ds, "id", "") for ds in db_systems if getattr(ds, "id", "")}
        for db_system in db_systems:
            try:
                rows.append(self._build_db_system_row(db_system))
            except Exception as exc:
                logger.exception(
                    "Failed to inventory DB system %s: %s",
                    getattr(db_system, "id", "unknown"),
                    exc,
                )

        # DB Homes are compartment-scoped; enumerate once and index by db_system_id
        db_homes_all = self._list_db_homes(compartment_id)
        for db_home in db_homes_all:
            try:
                rows.append(self._build_db_home_row(db_home))
            except Exception as exc:
                logger.warning(
                    "Failed to inventory DB home %s: %s",
                    getattr(db_home, "id", "unknown"),
                    exc,
                )

        # Databases MUST be listed per DB Home (or per DB System). The OCI
        # REST API rejects compartment-only calls with
        # "MissingParameter: dbHomeId or systemId required" even though the
        # Python SDK signature accepts a bare compartment_id.
        db_home_index: dict[str, Any] = {getattr(h, "id", ""): h for h in db_homes_all}
        databases_all: list[Any] = []
        seen_db_ids: set[str] = set()
        for db_home in db_homes_all:
            db_home_id = getattr(db_home, "id", "")
            if not db_home_id:
                continue
            for database in self._list_databases(compartment_id, db_home_id=db_home_id):
                dbid = getattr(database, "id", "")
                if dbid and dbid in seen_db_ids:
                    continue
                if dbid:
                    seen_db_ids.add(dbid)
                databases_all.append(database)
        # Fallback: also enumerate per DB System (system_id variant) so that
        # any databases not resolvable via db_home_id are still captured.
        for db_system_id in db_system_ids:
            for database in self._list_databases(compartment_id, system_id=db_system_id):
                dbid = getattr(database, "id", "")
                if dbid and dbid in seen_db_ids:
                    continue
                if dbid:
                    seen_db_ids.add(dbid)
                databases_all.append(database)
        for database in databases_all:
            try:
                rows.append(
                    self._build_database_row(
                        database,
                        db_home_index.get(getattr(database, "db_home_id", "")),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Failed to inventory database %s: %s",
                    getattr(database, "id", "unknown"),
                    exc,
                )

        # DB Nodes are compartment-scoped; SDK requires either db_system_id or
        # vm_cluster_id. Enumerate per DB System (already collected) and per
        # Cloud VM Cluster to cover Exadata Cloud Service.
        for db_system_id in db_system_ids:
            for db_node in self._list_db_nodes(compartment_id, db_system_id=db_system_id):
                try:
                    rows.append(self._build_db_node_row(db_node))
                except Exception as exc:
                    logger.warning(
                        "Failed to inventory DB node %s: %s",
                        getattr(db_node, "id", "unknown"),
                        exc,
                    )

        # Cloud VM Clusters (Exadata Cloud Service)
        for vm_cluster in self._list_cloud_vm_clusters(compartment_id):
            try:
                rows.append(self._build_cloud_vm_cluster_row(vm_cluster))
            except Exception as exc:
                logger.warning(
                    "Failed to inventory Cloud VM Cluster %s: %s",
                    getattr(vm_cluster, "id", "unknown"),
                    exc,
                )
            vm_cluster_id = getattr(vm_cluster, "id", "")
            if vm_cluster_id:
                for db_node in self._list_db_nodes(compartment_id, vm_cluster_id=vm_cluster_id):
                    try:
                        rows.append(self._build_db_node_row(db_node))
                    except Exception as exc:
                        logger.warning(
                            "Failed to inventory DB node %s: %s",
                            getattr(db_node, "id", "unknown"),
                            exc,
                        )

        # Cloud Exadata Infrastructures
        for exa in self._list_cloud_exadata_infrastructures(compartment_id):
            try:
                rows.append(self._build_cloud_exadata_row(exa))
            except Exception as exc:
                logger.warning(
                    "Failed to inventory Cloud Exadata Infrastructure %s: %s",
                    getattr(exa, "id", "unknown"),
                    exc,
                )

        # Autonomous Databases
        for adb in self._list_autonomous_databases(compartment_id):
            try:
                rows.append(self._build_autonomous_database_row(adb))
            except Exception as exc:
                logger.warning(
                    "Failed to inventory Autonomous Database %s: %s",
                    getattr(adb, "id", "unknown"),
                    exc,
                )

        return rows

    # --------------------------- LIST helpers ---------------------------

    def _list_db_systems(self, compartment_id: str) -> list[Any]:
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_db_systems,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning("Unable to list DB systems in compartment %s: %s", compartment_id, exc)
            return []

    def _list_db_homes(self, compartment_id: str) -> list[Any]:
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_db_homes,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning("Unable to list DB homes in compartment %s: %s", compartment_id, exc)
            return []

    def _list_databases(
        self,
        compartment_id: str,
        db_home_id: str | None = None,
        system_id: str | None = None,
    ) -> list[Any]:
        try:
            kwargs: dict[str, Any] = {"compartment_id": compartment_id}
            if db_home_id:
                kwargs["db_home_id"] = db_home_id
            if system_id:
                kwargs["system_id"] = system_id
            response = list_call_get_all_results(
                self.manager.database_client.list_databases,
                **kwargs,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning(
                "Unable to list databases (db_home=%s, system=%s): %s",
                db_home_id,
                system_id,
                exc,
            )
            return []

    def _list_db_nodes(
        self,
        compartment_id: str,
        db_system_id: str | None = None,
        vm_cluster_id: str | None = None,
    ) -> list[Any]:
        try:
            kwargs: dict[str, Any] = {"compartment_id": compartment_id}
            if db_system_id:
                kwargs["db_system_id"] = db_system_id
            if vm_cluster_id:
                kwargs["vm_cluster_id"] = vm_cluster_id
            response = list_call_get_all_results(
                self.manager.database_client.list_db_nodes,
                **kwargs,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning(
                "Unable to list DB nodes (db_system=%s, vm_cluster=%s): %s",
                db_system_id,
                vm_cluster_id,
                exc,
            )
            return []

    def _list_cloud_vm_clusters(self, compartment_id: str) -> list[Any]:
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_cloud_vm_clusters,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning("Unable to list Cloud VM Clusters in compartment %s: %s", compartment_id, exc)
            return []

    def _list_cloud_exadata_infrastructures(self, compartment_id: str) -> list[Any]:
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_cloud_exadata_infrastructures,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning(
                "Unable to list Cloud Exadata Infrastructures in compartment %s: %s",
                compartment_id,
                exc,
            )
            return []

    def _list_autonomous_databases(self, compartment_id: str) -> list[Any]:
        try:
            response = list_call_get_all_results(
                self.manager.database_client.list_autonomous_databases,
                compartment_id=compartment_id,
            )
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning(
                "Unable to list Autonomous Databases in compartment %s: %s", compartment_id, exc
            )
            return []

    # --------------------------- Row builders ---------------------------

    def _lookup_subnet_and_vcn(self, subnet_id: str) -> tuple[Any, Any]:
        """Resolve subnet + vcn objects, priming the cache."""
        subnet = None
        vcn = None
        if subnet_id:
            subnet = self.cache.get_subnet(subnet_id)
            if subnet is None:
                try:
                    subnet = self.manager.virtual_network_client.get_subnet(
                        subnet_id=subnet_id
                    ).data
                    self.cache.cache_subnet(subnet_id, subnet)
                except Exception as exc:
                    logger.warning("Unable to get subnet %s: %s", subnet_id, exc)
        if subnet is not None:
            vcn_id = getattr(subnet, "vcn_id", "")
            if vcn_id:
                vcn = self.cache.get_vcn(vcn_id)
                if vcn is None:
                    try:
                        vcn = self.manager.virtual_network_client.get_vcn(vcn_id=vcn_id).data
                        self.cache.cache_vcn(vcn_id, vcn)
                    except Exception as exc:
                        logger.warning("Unable to get VCN %s: %s", vcn_id, exc)
        return subnet, vcn

    def _build_db_system_row(self, db_system: Any) -> dict[str, Any]:
        subnet, vcn = self._lookup_subnet_and_vcn(getattr(db_system, "subnet_id", "") or "")
        fault_domains = getattr(db_system, "fault_domains", []) or []
        row = {
            "Resource Type": "DB System",
            "Name": getattr(db_system, "display_name", ""),
            "OCID": getattr(db_system, "id", ""),
            "Hostname": getattr(db_system, "hostname", "") or "",
            "Private IP": "",  # populated below via db_node vnic lookup if available
            "Domain": getattr(db_system, "domain", "") or "",
            "Cluster Name": getattr(db_system, "cluster_name", "") or "",
            "Database Edition": getattr(db_system, "database_edition", ""),
            "Version": getattr(db_system, "version", "") or "",
            "Shape": getattr(db_system, "shape", ""),
            "Lifecycle": getattr(db_system, "lifecycle_state", ""),
            "CPU Count": getattr(db_system, "cpu_core_count", ""),
            "Node Count": getattr(db_system, "node_count", ""),
            "Storage Size GB": getattr(db_system, "data_storage_size_in_gbs", ""),
            "Reco Storage GB": getattr(db_system, "reco_storage_size_in_gb", ""),
            "License Model": getattr(db_system, "license_model", "") or "",
            "Availability Domain": getattr(db_system, "availability_domain", ""),
            "Fault Domain": ", ".join(fault_domains),
            "Subnet Name": getattr(subnet, "display_name", "") if subnet is not None else "",
            "Subnet OCID": getattr(db_system, "subnet_id", "") or "",
            "VCN Name": getattr(vcn, "display_name", "") if vcn is not None else "",
            "VCN OCID": getattr(subnet, "vcn_id", "") if subnet is not None else "",
            "NSGs": ", ".join(getattr(db_system, "nsg_ids", []) or []),
            "Node Count Total": getattr(db_system, "node_count", "") or "",
        }

        # Enrich private IP via first DB node's VNIC when possible.
        try:
            db_system_id = getattr(db_system, "id", "")
            if db_system_id:
                nodes = self._list_db_nodes(
                    getattr(db_system, "compartment_id", ""),
                    db_system_id=db_system_id,
                )
                for node in nodes:
                    vnic_id = getattr(node, "vnic_id", "")
                    if not vnic_id:
                        continue
                    try:
                        vnic = self.manager.virtual_network_client.get_vnic(
                            vnic_id=vnic_id
                        ).data
                        row["Private IP"] = getattr(vnic, "private_ip", "") or ""
                        break
                    except Exception as exc:
                        logger.warning(
                            "Unable to resolve VNIC %s for DB node %s: %s",
                            vnic_id,
                            getattr(node, "id", ""),
                            exc,
                        )
        except Exception as exc:
            logger.warning(
                "Unable to enrich Private IP for DB system %s: %s",
                getattr(db_system, "id", ""),
                exc,
            )
        return row

    def _build_db_home_row(self, db_home: Any) -> dict[str, Any]:
        return {
            "Resource Type": "DB Home",
            "Name": getattr(db_home, "display_name", ""),
            "OCID": getattr(db_home, "id", ""),
            "DB System": getattr(db_home, "db_system_id", "") or "",
            "VM Cluster": getattr(db_home, "vm_cluster_id", "") or "",
            "Version": getattr(db_home, "db_version", "") or "",
            "Home Type": getattr(db_home, "home_type", "") or "",
            "Lifecycle": getattr(db_home, "lifecycle_state", ""),
        }

    def _build_database_row(self, database: Any, db_home: Any | None) -> dict[str, Any]:
        pdb_name = getattr(database, "pdb_name", "") or ""
        return {
            "Resource Type": "Database",
            "Name": getattr(database, "db_name", ""),
            "OCID": getattr(database, "id", ""),
            "Unique Name": getattr(database, "db_unique_name", "") or "",
            "PDB Name": pdb_name,
            "DB Home": getattr(database, "db_home_id", "") or "",
            "DB Home Name": getattr(db_home, "display_name", "") if db_home is not None else "",
            "DB System": getattr(database, "db_system_id", "") or "",
            "VM Cluster": getattr(database, "vm_cluster_id", "") or "",
            "Version": getattr(db_home, "db_version", "") if db_home is not None else "",
            "Admin User": getattr(database, "admin_user_name", "") or "",
            "Workload": getattr(database, "db_workload", "") or "",
            "Is CDB": getattr(database, "is_cdb", ""),
            "Character Set": getattr(database, "character_set", "") or "",
            "NCharacter Set": getattr(database, "ncharacter_set", "") or "",
            "Lifecycle": getattr(database, "lifecycle_state", ""),
        }

    def _build_db_node_row(self, db_node: Any) -> dict[str, Any]:
        row = {
            "Resource Type": "DB Node",
            "Name": getattr(db_node, "hostname", "") or "",
            "OCID": getattr(db_node, "id", ""),
            "Hostname": getattr(db_node, "hostname", "") or "",
            "DB System": getattr(db_node, "db_system_id", "") or "",
            "VM Cluster": getattr(db_node, "vm_cluster_id", "") or "",
            "VNIC": getattr(db_node, "vnic_id", "") or "",
            "Backup VNIC": getattr(db_node, "backup_vnic_id", "") or "",
            "Availability Domain": getattr(db_node, "availability_domain", "") or "",
            "Fault Domain": getattr(db_node, "fault_domain", "") or "",
            "Private IP": "",
            "Lifecycle": getattr(db_node, "lifecycle_state", ""),
        }
        vnic_id = getattr(db_node, "vnic_id", "") or ""
        if vnic_id:
            try:
                vnic = self.manager.virtual_network_client.get_vnic(vnic_id=vnic_id).data
                row["Private IP"] = getattr(vnic, "private_ip", "") or ""
            except Exception as exc:
                logger.warning(
                    "Unable to enrich DB node %s with VNIC %s: %s",
                    getattr(db_node, "id", ""),
                    vnic_id,
                    exc,
                )
        return row

    def _build_cloud_vm_cluster_row(self, vm_cluster: Any) -> dict[str, Any]:
        subnet, vcn = self._lookup_subnet_and_vcn(getattr(vm_cluster, "subnet_id", "") or "")
        return {
            "Resource Type": "Cloud VM Cluster",
            "Name": getattr(vm_cluster, "display_name", ""),
            "OCID": getattr(vm_cluster, "id", ""),
            "Hostname": getattr(vm_cluster, "hostname", "") or "",
            "Cluster Name": getattr(vm_cluster, "cluster_name", "") or "",
            "Shape": getattr(vm_cluster, "shape", "") or "",
            "CPU Count": getattr(vm_cluster, "cpu_core_count", "") or "",
            "Node Count": getattr(vm_cluster, "node_count", "") or "",
            "Storage Size GB": getattr(vm_cluster, "data_storage_size_in_tbs", "") or "",
            "License Model": getattr(vm_cluster, "license_model", "") or "",
            "Availability Domain": getattr(vm_cluster, "availability_domain", "") or "",
            "Subnet Name": getattr(subnet, "display_name", "") if subnet is not None else "",
            "Subnet OCID": getattr(vm_cluster, "subnet_id", "") or "",
            "VCN Name": getattr(vcn, "display_name", "") if vcn is not None else "",
            "VCN OCID": getattr(subnet, "vcn_id", "") if subnet is not None else "",
            "NSGs": ", ".join(getattr(vm_cluster, "nsg_ids", []) or []),
            "Lifecycle": getattr(vm_cluster, "lifecycle_state", ""),
        }

    def _build_cloud_exadata_row(self, exa: Any) -> dict[str, Any]:
        return {
            "Resource Type": "Cloud Exadata Infrastructure",
            "Name": getattr(exa, "display_name", ""),
            "OCID": getattr(exa, "id", ""),
            "Shape": getattr(exa, "shape", "") or "",
            "Availability Domain": getattr(exa, "availability_domain", "") or "",
            "Compute Count": getattr(exa, "compute_count", "") or "",
            "Storage Count": getattr(exa, "storage_count", "") or "",
            "Total Storage TB": getattr(exa, "total_storage_size_in_gbs", "") or "",
            "Lifecycle": getattr(exa, "lifecycle_state", ""),
        }

    def _build_autonomous_database_row(self, adb: Any) -> dict[str, Any]:
        return {
            "Resource Type": "Autonomous Database",
            "Name": getattr(adb, "display_name", ""),
            "OCID": getattr(adb, "id", ""),
            "DB Name": getattr(adb, "db_name", "") or "",
            "Workload": getattr(adb, "db_workload", "") or "",
            "Version": getattr(adb, "db_version", "") or "",
            "CPU Count": getattr(adb, "cpu_core_count", "") or getattr(adb, "compute_count", "") or "",
            "Storage TB": getattr(adb, "data_storage_size_in_tbs", "") or "",
            "License Model": getattr(adb, "license_model", "") or "",
            "Is Free Tier": getattr(adb, "is_free_tier", ""),
            "Is Dedicated": getattr(adb, "is_dedicated", ""),
            "Private Endpoint": getattr(adb, "private_endpoint", "") or "",
            "Private Endpoint IP": getattr(adb, "private_endpoint_ip", "") or "",
            "Subnet OCID": getattr(adb, "subnet_id", "") or "",
            "NSGs": ", ".join(getattr(adb, "nsg_ids", []) or []),
            "Lifecycle": getattr(adb, "lifecycle_state", ""),
        }
