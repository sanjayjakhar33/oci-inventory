"""VPN inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class VPNCollector:
    """Collect OCI VPN inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cpe in self._paginate(self.manager.virtual_network_client.list_cpes, compartment_id=compartment_id):
            try:
                self.cache.cache_cpe(getattr(cpe, "id", ""), cpe)
                rows.append({
                    "Resource Type": "CPE",
                    "Name": getattr(cpe, "display_name", ""),
                    "OCID": getattr(cpe, "id", ""),
                    "Public IP": getattr(cpe, "ip_address", ""),
                })
            except Exception as exc:
                logger.warning("Unable to inventory CPE %s: %s", getattr(cpe, "id", ""), exc)

        for connection in self._paginate(self.manager.virtual_network_client.list_ip_sec_connections, compartment_id=compartment_id):
            try:
                tunnels = self._paginate(
                    self.manager.virtual_network_client.list_ip_sec_connection_tunnels,
                    ipsc_id=getattr(connection, "id", ""),
                )
                tunnel_rows = []
                tunnel_ips = []
                static_routes = []
                for tunnel in tunnels:
                    tunnel_rows.append(
                        f"{getattr(tunnel, 'display_name', '')} ({getattr(tunnel, 'lifecycle_state', '')})"
                    )
                    if getattr(tunnel, "vpn_ip", None):
                        tunnel_ips.append(getattr(tunnel, "vpn_ip", ""))
                    if getattr(tunnel, "route_tables", None):
                        static_routes.extend(getattr(tunnel, "route_tables", []) or [])
                rows.append({
                    "Resource Type": "IPSec Connection",
                    "Name": getattr(connection, "display_name", ""),
                    "OCID": getattr(connection, "id", ""),
                    "CPE Name": getattr(connection, "cpe_id", ""),
                    "CPE Public IP": getattr(self.cache.get_cpe(getattr(connection, "cpe_id", "")), "ip_address", "") if self.cache.get_cpe(getattr(connection, "cpe_id", "")) else "",
                    "Customer LAN CIDRs": ", ".join(getattr(connection, "customer_bgp_asn", []) or []),
                    "DRG": getattr(connection, "drg_id", ""),
                    "Tunnel Public IPs": ", ".join(tunnel_ips),
                    "Tunnel Status": "; ".join(tunnel_rows),
                    "Static Routes": ", ".join(static_routes),
                })

                # Additive: one row per Customer LAN CIDR. Covers static
                # routes declared on the IPSec connection (STATIC routing)
                # and per-tunnel policy-based traffic selectors.
                ipsec_name = getattr(connection, "display_name", "") or ""
                ipsec_id = getattr(connection, "id", "") or ""
                for cidr in getattr(connection, "static_routes", []) or []:
                    rows.append({
                        "Resource Type": "IPSec Customer LAN",
                        "Name": cidr,
                        "OCID": ipsec_id,
                        "IPSec Name": ipsec_name,
                        "IPSec OCID": ipsec_id,
                        "Customer LAN CIDR": cidr,
                        "Routing Type": "STATIC",
                        "Tunnel": "",
                    })
                for tunnel in tunnels:
                    routing = getattr(tunnel, "routing", "") or ""
                    tunnel_name = getattr(tunnel, "display_name", "") or ""
                    if routing.upper() == "POLICY":
                        enc = getattr(tunnel, "encryption_domain_config", None)
                        cpe_selectors = getattr(enc, "cpe_traffic_selector", []) if enc else []
                        for cidr in cpe_selectors or []:
                            rows.append({
                                "Resource Type": "IPSec Customer LAN",
                                "Name": cidr,
                                "OCID": ipsec_id,
                                "IPSec Name": ipsec_name,
                                "IPSec OCID": ipsec_id,
                                "Customer LAN CIDR": cidr,
                                "Routing Type": "POLICY",
                                "Tunnel": tunnel_name,
                            })
            except Exception as exc:
                logger.warning("Unable to inventory IPSec connection %s: %s", getattr(connection, "id", ""), exc)
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
