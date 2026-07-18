"""Networking inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache, join_values

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
        rows.extend(self._collect_route_rules(compartment_id))
        rows.extend(self._collect_security_lists(compartment_id))
        rows.extend(self._collect_security_rules(compartment_id))
        rows.extend(self._collect_nsgs(compartment_id))
        rows.extend(self._collect_nsg_rules(compartment_id))
        rows.extend(self._collect_dhcp_options(compartment_id))
        rows.extend(self._collect_private_ips(compartment_id))
        rows.extend(self._collect_public_ips(compartment_id))
        return rows

    def _collect_vcns(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for vcn in self._paginate(self.manager.virtual_network_client.list_vcns, compartment_id=compartment_id):
            self.cache.cache_vcn(getattr(vcn, "id", ""), vcn)
            rows.append({
                "Resource Type": "VCN",
                "Name": getattr(vcn, "display_name", ""),
                "OCID": getattr(vcn, "id", ""),
                "CIDR Blocks": join_values(getattr(vcn, "cidr_blocks", []) or []),
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
                "Prohibit Public IP": getattr(subnet, "prohibit_public_ip_on_vnic", ""),
            })
        return rows

    def _collect_gateways(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        gateways = [
            ("Internet Gateway", self.manager.virtual_network_client.list_internet_gateways),
            ("NAT Gateway", self.manager.virtual_network_client.list_nat_gateways),
            ("Service Gateway", self.manager.virtual_network_client.list_service_gateways),
        ]
        for resource_type, list_method in gateways:
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

        try:
            attachments = self._paginate(
                self.manager.virtual_network_client.list_drg_attachments,
                compartment_id=compartment_id,
            )

            for attachment in attachments:
                rows.append({
                    "Resource Type": "DRG Attachment",
                    "Name": getattr(attachment, "display_name", ""),
                    "OCID": getattr(attachment, "id", ""),
                    "DRG": getattr(attachment, "drg_id", ""),
                    "VCN": getattr(attachment, "vcn_id", ""),
                    "Lifecycle": getattr(attachment, "lifecycle_state", ""),
                })

        except Exception as exc:
            logger.warning("Unable to list DRG attachments: %s", exc)

        for route_table in self._paginate(self.manager.virtual_network_client.list_drg_route_tables, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DRG Route Table",
                "Name": getattr(route_table, "display_name", ""),
                "OCID": getattr(route_table, "id", ""),
                "DRG": getattr(route_table, "drg_id", ""),
                "Lifecycle": getattr(route_table, "lifecycle_state", ""),
            })

        for distribution in self._paginate(self.manager.virtual_network_client.list_drg_route_distributions, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "DRG Route Distribution",
                "Name": getattr(distribution, "display_name", ""),
                "OCID": getattr(distribution, "id", ""),
                "DRG": getattr(distribution, "drg_id", ""),
                "Lifecycle": getattr(distribution, "lifecycle_state", ""),
            })
            try:
                statements = self._paginate(
                    self.manager.virtual_network_client.list_drg_route_distribution_statements,
                    drg_route_distribution_id=getattr(distribution, "id", ""),
                )
                for statement in statements:
                    rows.append({
                        "Resource Type": "DRG Route Distribution Statement",
                        "Name": getattr(statement, "display_name", ""),
                        "OCID": getattr(statement, "id", ""),
                        "DRG Route Distribution": getattr(distribution, "id", ""),
                        "Action": getattr(statement, "action", ""),
                        "Priority": getattr(statement, "priority", ""),
                    })
            except Exception as exc:
                logger.warning("Unable to enumerate DRG route distribution statements for %s: %s", getattr(distribution, "id", ""), exc)

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
            self.cache.cache_route_table(getattr(route_table, "id", ""), route_table)
            rows.append({
                "Resource Type": "Route Table",
                "Name": getattr(route_table, "display_name", ""),
                "OCID": getattr(route_table, "id", ""),
                "VCN": getattr(route_table, "vcn_id", ""),
                "Lifecycle": getattr(route_table, "lifecycle_state", ""),
            })
        return rows

    def _collect_route_rules(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for route_table in self._paginate(self.manager.virtual_network_client.list_route_tables, compartment_id=compartment_id):
            route_table_id = getattr(route_table, "id", "")
            try:
                details = self.manager.virtual_network_client.get_route_table(rt_id=route_table_id).data
                for rule in getattr(details, "route_rules", []) or []:
                    rows.append({
                        "Resource Type": "Route Rule",
                        "Name": getattr(rule, "destination", ""),
                        "OCID": route_table_id,
                        "Destination": getattr(rule, "destination", ""),
                        "Destination Type": getattr(rule, "destination_type", ""),
                        "Target": getattr(rule, "network_entity_id", ""),
                        "Description": getattr(rule, "description", ""),
                    })
            except Exception as exc:
                logger.warning("Unable to enrich route table %s: %s", route_table_id, exc)
        return rows

    def _collect_security_lists(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for security_list in self._paginate(self.manager.virtual_network_client.list_security_lists, compartment_id=compartment_id):
            self.cache.cache_security_list(getattr(security_list, "id", ""), security_list)
            rows.append({
                "Resource Type": "Security List",
                "Name": getattr(security_list, "display_name", ""),
                "OCID": getattr(security_list, "id", ""),
                "VCN": getattr(security_list, "vcn_id", ""),
                "Lifecycle": getattr(security_list, "lifecycle_state", ""),
            })
        return rows

    def _collect_security_rules(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for security_list in self._paginate(self.manager.virtual_network_client.list_security_lists, compartment_id=compartment_id):
            security_list_id = getattr(security_list, "id", "")
            try:
                details = self.manager.virtual_network_client.get_security_list(security_list_id=security_list_id).data
                for rule in getattr(details, "ingress_security_rules", []) or []:
                    rows.append({
                        "Resource Type": "Security List Rule",
                        "Name": getattr(security_list, "display_name", ""),
                        "OCID": security_list_id,
                        "Direction": "Ingress",
                        "Protocol": getattr(rule, "protocol", ""),
                        "Source": getattr(rule, "source", ""),
                        "Destination": getattr(rule, "destination", ""),
                        "Description": getattr(rule, "description", ""),
                    })
                for rule in getattr(details, "egress_security_rules", []) or []:
                    rows.append({
                        "Resource Type": "Security List Rule",
                        "Name": getattr(security_list, "display_name", ""),
                        "OCID": security_list_id,
                        "Direction": "Egress",
                        "Protocol": getattr(rule, "protocol", ""),
                        "Source": getattr(rule, "source", ""),
                        "Destination": getattr(rule, "destination", ""),
                        "Description": getattr(rule, "description", ""),
                    })
            except Exception as exc:
                logger.warning("Unable to enrich security list %s: %s", security_list_id, exc)
        return rows

    def _collect_nsgs(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for nsg in self._paginate(self.manager.virtual_network_client.list_network_security_groups, compartment_id=compartment_id):
            self.cache.cache_nsg(getattr(nsg, "id", ""), nsg)
            rows.append({
                "Resource Type": "NSG",
                "Name": getattr(nsg, "display_name", ""),
                "OCID": getattr(nsg, "id", ""),
                "VCN": getattr(nsg, "vcn_id", ""),
                "Lifecycle": getattr(nsg, "lifecycle_state", ""),
            })
        return rows

    def _collect_nsg_rules(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for nsg in self._paginate(self.manager.virtual_network_client.list_network_security_groups, compartment_id=compartment_id):
            nsg_id = getattr(nsg, "id", "")
            nsg_name = getattr(nsg, "display_name", "")
            try:
                rules = self._paginate(
                    self.manager.virtual_network_client.list_network_security_group_security_rules,
                    network_security_group_id=nsg_id,
                )
                for rule in rules:
                    rows.append({
                        "Resource Type": "NSG Rule",
                        "Name": nsg_name,
                        "NSG Name": nsg_name,
                        "NSG OCID": nsg_id,
                        "OCID": nsg_id,
                        "Rule ID": getattr(rule, "id", ""),
                        "Direction": getattr(rule, "direction", ""),
                        "Protocol": getattr(rule, "protocol", ""),
                        "Source": getattr(rule, "source", "") or "",
                        "Destination": getattr(rule, "destination", "") or "",
                        "Source Type": getattr(rule, "source_type", "") or "",
                        "Destination Type": getattr(rule, "destination_type", "") or "",
                        "TCP Options": str(getattr(rule, "tcp_options", "") or ""),
                        "UDP Options": str(getattr(rule, "udp_options", "") or ""),
                        "ICMP Options": str(getattr(rule, "icmp_options", "") or ""),
                        "Is Stateless": getattr(rule, "is_stateless", ""),
                        "Is Valid": getattr(rule, "is_valid", ""),
                        "Description": getattr(rule, "description", "") or "",
                    })
            except Exception as exc:
                logger.warning("Unable to inspect NSG rules for %s: %s", nsg_id, exc)
        return rows

    def _collect_dhcp_options(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for dhcp in self._paginate(self.manager.virtual_network_client.list_dhcp_options, compartment_id=compartment_id):
            self.cache.cache_dhcp_options(getattr(dhcp, "id", ""), dhcp)
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
        # list_private_ips filters by subnet_id / vnic_id / vlan_id — it does
        # not accept scope or compartment_id. Enumerate per subnet in the
        # target compartment to build a complete private-IP inventory.
        for subnet in self._paginate(
            self.manager.virtual_network_client.list_subnets,
            compartment_id=compartment_id,
        ):
            subnet_id = getattr(subnet, "id", "")
            if not subnet_id:
                continue
            for private_ip in self._paginate(
                self.manager.virtual_network_client.list_private_ips,
                subnet_id=subnet_id,
            ):
                rows.append({
                    "Resource Type": "Private IP",
                    "Name": getattr(private_ip, "display_name", ""),
                    "OCID": getattr(private_ip, "id", ""),
                    "IP Address": getattr(private_ip, "ip_address", ""),
                    "Subnet": getattr(private_ip, "subnet_id", "") or subnet_id,
                    "VCN": getattr(private_ip, "vcn_id", "") or getattr(subnet, "vcn_id", ""),
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
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
