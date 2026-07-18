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
                # Consolidated Customer LAN inventory (previously emitted as a
                # separate "IPSec Customer LAN" sheet). All Customer LAN data
                # is now flattened onto the IPSec Connection row.
                routing_types: list[str] = []
                traffic_selectors: list[str] = []
                # Connection-level static_routes = customer LAN CIDRs for
                # STATIC-routed connections.
                connection_static_routes = list(getattr(connection, "static_routes", []) or [])
                if connection_static_routes:
                    routing_types.append("STATIC")
                for tunnel in tunnels:
                    tunnel_rows.append(
                        f"{getattr(tunnel, 'display_name', '')} ({getattr(tunnel, 'lifecycle_state', '')})"
                    )
                    if getattr(tunnel, "vpn_ip", None):
                        tunnel_ips.append(getattr(tunnel, "vpn_ip", ""))
                    if getattr(tunnel, "route_tables", None):
                        static_routes.extend(getattr(tunnel, "route_tables", []) or [])
                    routing = (getattr(tunnel, "routing", "") or "").upper()
                    if routing and routing not in routing_types:
                        routing_types.append(routing)
                    if routing == "POLICY":
                        enc = getattr(tunnel, "encryption_domain_config", None)
                        cpe_selectors = getattr(enc, "cpe_traffic_selector", []) if enc else []
                        tunnel_name = getattr(tunnel, "display_name", "") or ""
                        for cidr in cpe_selectors or []:
                            traffic_selectors.append(
                                f"{tunnel_name}:{cidr}" if tunnel_name else cidr
                            )
                # Merge connection-level static routes into the Customer LAN
                # CIDR list (previously incorrectly sourced from
                # customer_bgp_asn, which is a BGP ASN string, not a CIDR).
                customer_lan_cidrs = connection_static_routes
                rows.append({
                    "Resource Type": "IPSec Connection",
                    "Name": getattr(connection, "display_name", ""),
                    "OCID": getattr(connection, "id", ""),
                    "CPE Name": getattr(connection, "cpe_id", ""),
                    "CPE Public IP": getattr(self.cache.get_cpe(getattr(connection, "cpe_id", "")), "ip_address", "") if self.cache.get_cpe(getattr(connection, "cpe_id", "")) else "",
                    "Customer LAN CIDRs": ", ".join(customer_lan_cidrs),
                    "Routing Type": ", ".join(routing_types),
                    "Traffic Selectors": ", ".join(traffic_selectors),
                    "DRG": getattr(connection, "drg_id", ""),
                    "Tunnel Public IPs": ", ".join(tunnel_ips),
                    "Tunnel Status": "; ".join(tunnel_rows),
                    "Static Routes": ", ".join(static_routes),
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
