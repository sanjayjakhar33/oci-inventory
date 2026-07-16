"""Load balancer inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class LoadBalancerCollector:
    """Collect OCI load balancer inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for load_balancer in self._paginate(self.manager.load_balancer_client.list_load_balancers, compartment_id=compartment_id):
            try:
                lb = self.manager.load_balancer_client.get_load_balancer(load_balancer_id=getattr(load_balancer, "id", "")).data
                public_ips = [
                    getattr(address, "ip_address", "")
                    for address in getattr(lb, "ip_addresses", [])
                    if getattr(address, "ip_address", None)
                ]
                rows.append({
                    "LB Name": getattr(lb, "display_name", ""),
                    "OCID": getattr(lb, "id", ""),
                    "Private IP": "",
                    "Public IP": ", ".join(public_ips),
                    "Shape": getattr(lb, "shape_name", ""),
                    "Subnet": getattr(load_balancer, "subnet_ids", [""])[0],
                    "VCN": "",
                    "NSGs": "",
                    "Backend Sets": "",
                    "Backends": "",
                    "Listeners": "",
                })
            except Exception as exc:
                logger.warning("Unable to inventory load balancer %s: %s", getattr(load_balancer, "id", ""), exc)
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            return list(list_call_get_all_results(list_method, **kwargs))
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
