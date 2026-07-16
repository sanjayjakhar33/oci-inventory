"""DNS inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class DNSCollector:
    """Collect OCI DNS zones, views, and resolvers for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_zones(compartment_id))
        rows.extend(self._collect_views(compartment_id))
        rows.extend(self._collect_resolvers(compartment_id))
        return rows

    def _collect_zones(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for zone in self._paginate(self.manager.dns_client.list_zones, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Zone",
                "Name": getattr(zone, "name", ""),
                "OCID": getattr(zone, "id", ""),
                "Scope": getattr(zone, "scope", ""),
                "Lifecycle": getattr(zone, "lifecycle_state", ""),
            })
        return rows

    def _collect_views(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for view in self._paginate(self.manager.dns_client.list_views, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "View",
                "Name": getattr(view, "display_name", ""),
                "OCID": getattr(view, "id", ""),
                "Scope": getattr(view, "scope", ""),
                "Lifecycle": getattr(view, "lifecycle_state", ""),
            })
        return rows

    def _collect_resolvers(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for resolver in self._paginate(self.manager.dns_client.list_resolvers, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Resolver",
                "Name": getattr(resolver, "display_name", ""),
                "OCID": getattr(resolver, "id", ""),
                "Scope": getattr(resolver, "scope", ""),
                "Lifecycle": getattr(resolver, "lifecycle_state", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
