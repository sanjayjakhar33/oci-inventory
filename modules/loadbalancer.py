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
                backend_sets = self._paginate(
                    self.manager.load_balancer_client.list_backend_sets,
                    load_balancer_id=getattr(load_balancer, "id", ""),
                )
                backend_rows = []
                for backend_set in backend_sets:
                    backend_names = []
                    for backend in self._paginate(
                        self.manager.load_balancer_client.list_backends,
                        load_balancer_id=getattr(load_balancer, "id", ""),
                        backend_set_name=getattr(backend_set, "name", ""),
                    ):
                        backend_names.append(getattr(backend, "name", ""))
                    backend_rows.append(f"{getattr(backend_set, 'name', '')}: {', '.join(backend_names)}")

                listener_rows = []
                for certificate in self._paginate(
                    self.manager.load_balancer_client.list_certificates,
                    load_balancer_id=getattr(load_balancer, "id", ""),
                ):
                    listener_rows.append(f"Certificate: {getattr(certificate, 'display_name', '')}")
                for hostname in self._paginate(
                    self.manager.load_balancer_client.list_hostnames,
                    load_balancer_id=getattr(load_balancer, "id", ""),
                ):
                    listener_rows.append(f"Hostname: {getattr(hostname, 'hostname', '')}")

                rows.append({
                    "Resource Type": "Load Balancer",
                    "LB Name": getattr(lb, "display_name", ""),
                    "OCID": getattr(lb, "id", ""),
                    "Private IP": "",
                    "Public IP": ", ".join(public_ips),
                    "Shape": getattr(lb, "shape_name", ""),
                    "Subnet": getattr(load_balancer, "subnet_ids", [""])[0],
                    "VCN": "",
                    "NSGs": ", ".join(getattr(load_balancer, "nsg_ids", []) or []),
                    "Backend Sets": "; ".join(backend_rows),
                    "Backends": "",
                    "Listeners": "; ".join(listener_rows),
                })
            except Exception as exc:
                logger.warning("Unable to inventory load balancer %s: %s", getattr(load_balancer, "id", ""), exc)
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
