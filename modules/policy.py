"""IAM policy inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class PolicyCollector:
    """Collect OCI IAM policies for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for policy in self._paginate(self.manager.identity_client.list_policies, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "IAM Policy",
                "Name": getattr(policy, "name", ""),
                "OCID": getattr(policy, "id", ""),
                "Description": getattr(policy, "description", ""),
                "Lifecycle": getattr(policy, "lifecycle_state", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
