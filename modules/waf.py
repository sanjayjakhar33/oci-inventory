"""WAF inventory collector."""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class WAFCollector:
    """Collect OCI WAF policies, domains, origins, and certificates."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_policies(compartment_id))
        rows.extend(self._collect_certificates(compartment_id))
        return rows

    def _collect_policies(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for policy in self._paginate(self.manager.waas_client.list_waas_policies, compartment_id=compartment_id):
            try:
                policy_details = self.manager.waas_client.get_waas_policy(waas_policy_id=getattr(policy, "id", "")).data
                domains = []
                if getattr(policy_details, "domain_name", None):
                    domains.append(getattr(policy_details, "domain_name", ""))
                origins = []
                for origin in getattr(policy_details, "origin", []) or []:
                    origins.append(getattr(origin, "uri", ""))
                rows.append({
                    "Resource Type": "Policy",
                    "Name": getattr(policy, "display_name", ""),
                    "OCID": getattr(policy, "id", ""),
                    "Domains": ", ".join(domains),
                    "Origins": ", ".join(origins),
                    "Lifecycle": getattr(policy, "lifecycle_state", ""),
                })
            except Exception as exc:
                logger.warning("Unable to enrich WAF policy %s: %s", getattr(policy, "id", ""), exc)
                rows.append({
                    "Resource Type": "Policy",
                    "Name": getattr(policy, "display_name", ""),
                    "OCID": getattr(policy, "id", ""),
                    "Domains": "",
                    "Origins": "",
                    "Lifecycle": getattr(policy, "lifecycle_state", ""),
                })
        return rows

    def _collect_certificates(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for certificate in self._paginate(self.manager.waas_client.list_certificates, compartment_id=compartment_id):
            rows.append({
                "Resource Type": "Certificate",
                "Name": getattr(certificate, "display_name", ""),
                "OCID": getattr(certificate, "id", ""),
                "Lifecycle": getattr(certificate, "lifecycle_state", ""),
            })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            return list(list_call_get_all_results(list_method, **kwargs))
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
