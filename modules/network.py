"""Networking inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class NetworkCollector:
    """Collect OCI networking resources used by a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_vcns(compartment_id))
        rows.extend(self._collect_subnets(compartment_id))
        rows.extend(self._collect_gateways(compartment_id))
        rows.extend(self._collect_drg_resources(compartment_id))
        rows.extend(self._collect_route_tables(compartment_id))
        rows.extend(self._collect_security_lists(compartment_id))
        rows.extend(self._collect_dhcp_options(compartment_id))
        rows.extend(self._collect_private_ips(compartment_id))
        rows.extend(self._collect_public_ips(compartment_id))
        return rows

    def _collect_vcns(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for vcn in self._paginate(self.manager.virtual_network_client.list_vcns, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "VCN",
                "Name": getattr(vcn, "display_name", ""),
                "OCID": getattr(vcn, "id", ""),
                "CIDR Blocks": ", ".join(getattr(vcn, "cidr_blocks", []) or []),
                "Lifecycle": getattr(vcn, "lifecycle_state", ""),
                "DNS Label": getattr(vcn, "dns_label", ""),
            })
        return rows

    def _collect_subnets(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for subnet in self._paginate(self.manager.virtual_network_client.list_subnets, compartment_id=compartment_id):
            self.cache.cache_subnet(getattr(subnet, "id", ""), subnet)
            rows.append({
                "Resource Type": "Subnet",
                "Name": getattr(subnet, "display_name", ""),
                "OCID": getattr(subnet, "id", ""),
                "VCN": getattr(subnet, "vcn_id", ""),
                "CIDR": getattr(subnet, "cidr_block", ""),
                "Lifecycle": getattr(subnet, "lifecycle_state", ""),
            })
        return rows

    def _collect_gateways(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        gateways = [
            ("Internet Gateway", self.manager.virtual_network_client.list_internet_gateways, "internet_gateway"),
            ("NAT Gateway", self.manager.virtual_network_client.list_nat_gateways, "nat_gateway"),
            ("Service Gateway", self.manager.virtual_network_client.list_service_gateways, "service_gateway"),
        ]
        for resource_type, list_method, _ in gateways:
            for gateway in self._paginate(list_method, compartment_id=compartment_id):
                rows.append({
                    "Resource Type": resource_type,
                    "Name": getattr(gateway, "display_name", ""),
                    "OCID": getattr(gateway, "id", ""),
                    "VCN": getattr(gateway, "vcn_id", ""),
                    "Lifecycle": getattr(gateway, "lifecycle_state", ""),
                })
        return rows

    def _collect_drg_resources(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for drg in self._paginate(self.manager.virtual_network_client.list_drgs, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DRG",
                "Name": getattr(drg, "display_name", ""),
                "OCID": getattr(drg, "id", ""),
                "Lifecycle": getattr(drg, "lifecycle_state", ""),
            })

        for rpc in self._paginate(self.manager.virtual_network_client.list_remote_peering_connections, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Remote Peering Connection",
                "Name": getattr(rpc, "display_name", ""),
                "OCID": getattr(rpc, "id", ""),
                "DRG": getattr(rpc, "drg_id", ""),
                "Lifecycle": getattr(rpc, "lifecycle_state", ""),
            })

        for lpg in self._paginate(self.manager.virtual_network_client.list_local_peering_gateways, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Local Peering Gateway",
                "Name": getattr(lpg, "display_name", ""),
                "OCID": getattr(lpg, "id", ""),
                "VCN": getattr(lpg, "vcn_id", ""),
                "Lifecycle": getattr(lpg, "lifecycle_state", ""),
            })
        return rows

    def _collect_route_tables(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for route_table in self._paginate(self.manager.virtual_network_client.list_route_tables, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Route Table",
                "Name": getattr(route_table, "display_name", ""),
                "OCID": getattr(route_table, "id", ""),
                "VCN": getattr(route_table, "vcn_id", ""),
                "Lifecycle": getattr(route_table, "lifecycle_state", ""),
            })
        return rows

    def _collect_security_lists(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for security_list in self._paginate(self.manager.virtual_network_client.list_security_lists, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Security List",
                "Name": getattr(security_list, "display_name", ""),
                "OCID": getattr(security_list, "id", ""),
                "VCN": getattr(security_list, "vcn_id", ""),
                "Lifecycle": getattr(security_list, "lifecycle_state", ""),
            })
        return rows

    def _collect_dhcp_options(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for dhcp in self._paginate(self.manager.virtual_network_client.list_dhcp_options, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DHCP Options",
                "Name": getattr(dhcp, "display_name", ""),
                "OCID": getattr(dhcp, "id", ""),
                "VCN": getattr(dhcp, "vcn_id", ""),
                "Lifecycle": getattr(dhcp, "lifecycle_state", ""),
            })
        return rows

    def _collect_private_ips(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for private_ip in self._paginate(
            self.manager.virtual_network_client.list_private_ips,
            scope="REGION",
            compartment_id=compartment_id,
        ):
            rows.append({
                "Resource Type": "Private IP",
                "Name": getattr(private_ip, "display_name", ""),
                "OCID": getattr(private_ip, "id", ""),
                "IP Address": getattr(private_ip, "ip_address", ""),
                "Subnet": getattr(private_ip, "subnet_id", ""),
                "VCN": getattr(private_ip, "vcn_id", ""),
            })
        return rows

    def _collect_public_ips(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for public_ip in self._paginate(
            self.manager.virtual_network_client.list_public_ips,
            scope="REGION",
            compartment_id=compartment_id,
        ):
            rows.append({
                "Resource Type": "Public IP",
                "Name": getattr(public_ip, "display_name", ""),
                "OCID": getattr(public_ip, "id", ""),
                "IP Address": getattr(public_ip, "ip_address", ""),
                "Lifecycle": getattr(public_ip, "lifecycle_state", ""),
                "Scope": getattr(public_ip, "scope", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            return list(list_call_get_all_results(list_method, **kwargs))
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
