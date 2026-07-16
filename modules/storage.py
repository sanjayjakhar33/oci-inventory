"""Storage inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class StorageCollector:
    """Collect OCI storage inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_buckets(compartment_id))
        rows.extend(self._collect_block_volumes(compartment_id))
        rows.extend(self._collect_boot_volumes(compartment_id))
        rows.extend(self._collect_volume_groups(compartment_id))
        rows.extend(self._collect_volume_backups(compartment_id))
        rows.extend(self._collect_volume_group_backups(compartment_id))
        return rows

    def _collect_buckets(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        try:
            namespace = self.manager.object_storage_client.get_namespace().data
            for bucket in self._paginate(
                self.manager.object_storage_client.list_buckets,
                namespace_name=namespace,
                compartment_id=compartment_id,
                fields=["name", "compartment_id"],
            ):
                rows.append({
                    "Resource Type": "Bucket",
                    "Name": getattr(bucket, "name", ""),
                    "OCID": getattr(bucket, "id", ""),
                    "Compartment": getattr(bucket, "compartment_id", ""),
                    "Namespace": namespace,
                })
        except Exception as exc:
            logger.warning("Unable to inventory buckets: %s", exc)
        return rows

    def _collect_block_volumes(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for volume in self._paginate(self.manager.blockstorage_client.list_volumes, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Block Volume",
                "Name": getattr(volume, "display_name", ""),
                "OCID": getattr(volume, "id", ""),
                "Size": getattr(volume, "size_in_gbs", ""),
                "Availability Domain": getattr(volume, "availability_domain", ""),
                "Lifecycle": getattr(volume, "lifecycle_state", ""),
            })
        return rows

    def _collect_boot_volumes(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for boot_volume in self._paginate(self.manager.blockstorage_client.list_boot_volumes, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Boot Volume",
                "Name": getattr(boot_volume, "display_name", ""),
                "OCID": getattr(boot_volume, "id", ""),
                "Size": getattr(boot_volume, "size_in_gbs", ""),
                "Availability Domain": getattr(boot_volume, "availability_domain", ""),
                "Lifecycle": getattr(boot_volume, "lifecycle_state", ""),
            })
        return rows

    def _collect_volume_groups(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for volume_group in self._paginate(self.manager.blockstorage_client.list_volume_groups, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Volume Group",
                "Name": getattr(volume_group, "display_name", ""),
                "OCID": getattr(volume_group, "id", ""),
                "Availability Domain": getattr(volume_group, "availability_domain", ""),
                "Lifecycle": getattr(volume_group, "lifecycle_state", ""),
            })
        return rows

    def _collect_volume_backups(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for backup in self._paginate(self.manager.blockstorage_client.list_volume_backups, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Volume Backup",
                "Name": getattr(backup, "display_name", ""),
                "OCID": getattr(backup, "id", ""),
                "Volume": getattr(backup, "volume_id", ""),
                "Lifecycle": getattr(backup, "lifecycle_state", ""),
            })
        return rows

    def _collect_volume_group_backups(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for backup in self._paginate(self.manager.blockstorage_client.list_volume_group_backups, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Volume Group Backup",
                "Name": getattr(backup, "display_name", ""),
                "OCID": getattr(backup, "id", ""),
                "Volume Group": getattr(backup, "volume_group_id", ""),
                "Lifecycle": getattr(backup, "lifecycle_state", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
