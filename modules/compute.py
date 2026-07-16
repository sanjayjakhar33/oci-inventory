"""Compute inventory collector.

This module performs read-only inventory collection for OCI compute resources.
The flow resolves VNIC attachments through the VNIC, subnet, and VCN hierarchy,
then enriches the record with NSG names and boot volume metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache, to_iso_string

logger = logging.getLogger(__name__)


class ComputeCollector:
    """Collect OCI compute instance inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache
        self.logger = logger

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        """Return compute inventory rows for the target compartment."""
        rows: list[dict[str, Any]] = []
        for instance in self._list_instances(compartment_id):
            try:
                rows.append(self._build_instance_row(compartment_id, instance))
            except Exception as exc:
                self.logger.exception("Failed to inventory instance %s: %s", getattr(instance, "id", "unknown"), exc)
        return rows

    def _list_instances(self, compartment_id: str) -> list[Any]:
        try:
            return list(list_call_get_all_results(self.manager.compute_client.list_instances, compartment_id=compartment_id))
        except Exception as exc:
            self.logger.warning("Unable to list instances in compartment %s: %s", compartment_id, exc)
            return []

    def _list_vnic_attachments(self, compartment_id: str, instance_id: str) -> list[Any]:
        try:
            return list(
                list_call_get_all_results(
                    self.manager.compute_client.list_vnic_attachments,
                    compartment_id=compartment_id,
                    instance_id=instance_id,
                )
            )
        except Exception as exc:
            self.logger.warning("Unable to list VNIC attachments for instance %s: %s", instance_id, exc)
            return []

    def _get_vnic(self, vnic_id: str) -> Any | None:
        if not vnic_id:
            return None
        try:
            return self.manager.virtual_network_client.get_vnic(vnic_id=vnic_id).data
        except Exception as exc:
            self.logger.warning("Unable to get VNIC %s: %s", vnic_id, exc)
            return None

    def _get_subnet(self, subnet_id: str) -> Any | None:
        if not subnet_id:
            return None
        cached = self.cache.get_subnet(subnet_id)
        if cached is not None:
            return cached
        try:
            subnet = self.manager.virtual_network_client.get_subnet(subnet_id=subnet_id).data
            self.cache.cache_subnet(subnet_id, subnet)
            return subnet
        except Exception as exc:
            self.logger.warning("Unable to get subnet %s: %s", subnet_id, exc)
            return None

    def _get_vcn(self, vcn_id: str) -> Any | None:
        if not vcn_id:
            return None
        cached = self.cache.get_vcn(vcn_id)
        if cached is not None:
            return cached
        try:
            vcn = self.manager.virtual_network_client.get_vcn(vcn_id=vcn_id).data
            self.cache.cache_vcn(vcn_id, vcn)
            return vcn
        except Exception as exc:
            self.logger.warning("Unable to get VCN %s: %s", vcn_id, exc)
            return None

    def _get_nsg(self, nsg_id: str) -> Any | None:
        if not nsg_id:
            return None
        cached = self.cache.get_nsg(nsg_id)
        if cached is not None:
            return cached
        try:
            nsg = self.manager.virtual_network_client.get_network_security_group(network_security_group_id=nsg_id).data
            self.cache.cache_nsg(nsg_id, nsg)
            return nsg
        except Exception as exc:
            self.logger.warning("Unable to get NSG %s: %s", nsg_id, exc)
            return None

    def _list_boot_volume_attachments(self, compartment_id: str, instance_id: str) -> list[Any]:
        try:
            return list(
                list_call_get_all_results(
                    self.manager.compute_client.list_boot_volume_attachments,
                    compartment_id=compartment_id,
                    instance_id=instance_id,
                )
            )
        except Exception as exc:
            self.logger.warning("Unable to list boot volume attachments for instance %s: %s", instance_id, exc)
            return []

    def _get_boot_volume(self, boot_volume_id: str) -> Any | None:
        if not boot_volume_id:
            return None
        try:
            return self.manager.blockstorage_client.get_boot_volume(boot_volume_id=boot_volume_id).data
        except Exception as exc:
            self.logger.warning("Unable to get boot volume %s: %s", boot_volume_id, exc)
            return None

    def _build_instance_row(self, compartment_id: str, instance: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "Instance Name": getattr(instance, "display_name", ""),
            "Instance OCID": getattr(instance, "id", ""),
            "Availability Domain": getattr(instance, "availability_domain", ""),
            "Fault Domain": getattr(instance, "fault_domain", ""),
            "Lifecycle": getattr(instance, "lifecycle_state", ""),
            "Shape": getattr(instance, "shape", ""),
            "Image OCID": getattr(instance, "image_id", ""),
            "Private IP": "",
            "Public IP": "",
            "Subnet Name": "",
            "Subnet OCID": "",
            "VCN Name": "",
            "VCN OCID": "",
            "NSG Names": "",
            "NSG OCIDs": "",
            "Boot Volume Name": "",
            "Boot Volume Size": "",
            "Freeform Tags": getattr(instance, "freeform_tags", {}) or {},
            "Defined Tags": getattr(instance, "defined_tags", {}) or {},
            "Creation Time": to_iso_string(getattr(instance, "time_created", None)),
        }

        attachments = self._list_vnic_attachments(compartment_id, getattr(instance, "id", ""))
        attachment = attachments[0] if attachments else None
        if attachment is not None:
            vnic = self._get_vnic(getattr(attachment, "vnic_id", ""))
            if vnic is not None:
                row["Private IP"] = getattr(vnic, "private_ip", "")
                row["Public IP"] = getattr(vnic, "public_ip", "")
                row["Subnet OCID"] = getattr(vnic, "subnet_id", "")
                subnet = self._get_subnet(getattr(vnic, "subnet_id", ""))
                if subnet is not None:
                    row["Subnet Name"] = getattr(subnet, "display_name", "")
                    vcn = self._get_vcn(getattr(subnet, "vcn_id", ""))
                    if vcn is not None:
                        row["VCN Name"] = getattr(vcn, "display_name", "")
                        row["VCN OCID"] = getattr(vcn, "id", "")

                nsg_ids = getattr(vnic, "nsg_ids", []) or []
                nsg_names = []
                for nsg_id in nsg_ids:
                    nsg = self._get_nsg(nsg_id)
                    if nsg is not None:
                        nsg_names.append(getattr(nsg, "display_name", nsg_id))
                row["NSG Names"] = ", ".join(nsg_names)
                row["NSG OCIDs"] = ", ".join(nsg_ids)

        boot_attachments = self._list_boot_volume_attachments(compartment_id, getattr(instance, "id", ""))
        boot_attachment = boot_attachments[0] if boot_attachments else None
        boot_volume = self._get_boot_volume(getattr(boot_attachment, "boot_volume_id", "")) if boot_attachment else None
        if boot_volume is not None:
            row["Boot Volume Name"] = getattr(boot_volume, "display_name", "")
            row["Boot Volume Size"] = getattr(boot_volume, "size_in_gbs", "")

        return row
