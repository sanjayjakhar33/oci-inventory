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
        # Additive: private DNS zones + records for both public and private zones.
        rows.extend(self._collect_private_zones(compartment_id))
        rows.extend(self._collect_zone_records(compartment_id))
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

    def _build_view_to_vcn_index(self, compartment_id: str) -> dict[str, list[str]]:
        """Return a mapping of view OCID -> list of attached VCN OCIDs.

        Private DNS zones associate to VCNs via their view; resolvers own
        both attached_vcn_id and attached_views. Walk the resolvers once and
        build the index so per-zone lookups stay O(1) without extra calls.
        """
        index: dict[str, list[str]] = {}
        try:
            resolvers = self._paginate(
                self.manager.dns_client.list_resolvers,
                compartment_id=compartment_id,
                scope="PRIVATE",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unable to enumerate private resolvers: %s", exc)
            resolvers = []
        for resolver in resolvers:
            vcn_id = getattr(resolver, "attached_vcn_id", "") or ""
            if not vcn_id:
                continue
            default_view = getattr(resolver, "default_view_id", "") or ""
            if default_view:
                index.setdefault(default_view, []).append(vcn_id)
            # Some resolvers expose the full attached_views only via GET
            try:
                details = self.manager.dns_client.get_resolver(
                    resolver_id=getattr(resolver, "id", ""),
                    scope="PRIVATE",
                ).data
                for av in getattr(details, "attached_views", []) or []:
                    view_id = getattr(av, "view_id", "") or ""
                    if view_id:
                        index.setdefault(view_id, []).append(vcn_id)
            except Exception as exc:
                logger.warning(
                    "Unable to fetch resolver details %s: %s",
                    getattr(resolver, "id", ""),
                    exc,
                )
        # De-duplicate
        return {view_id: sorted(set(vcns)) for view_id, vcns in index.items()}

    def _collect_private_zones(self, compartment_id: str) -> list[dict[str, Any]]:
        """Enumerate zones with scope=PRIVATE and expose view / VCN linkage."""
        rows: list[dict[str, Any]] = []
        view_to_vcns = self._build_view_to_vcn_index(compartment_id)
        # Cache view display names for the "Private View" column.
        view_names: dict[str, str] = {}
        try:
            for view in self._paginate(
                self.manager.dns_client.list_views,
                compartment_id=compartment_id,
                scope="PRIVATE",
            ):
                vid = getattr(view, "id", "") or ""
                if vid:
                    view_names[vid] = getattr(view, "display_name", "") or ""
        except Exception as exc:
            logger.warning("Unable to enumerate private views: %s", exc)

        try:
            zones = self._paginate(
                self.manager.dns_client.list_zones,
                compartment_id=compartment_id,
                scope="PRIVATE",
            )
        except Exception as exc:
            logger.warning("Unable to enumerate private DNS zones: %s", exc)
            zones = []

        for zone in zones:
            view_id = getattr(zone, "view_id", "") or ""
            rows.append({
                "Resource Type": "Private DNS Zone",
                "Name": getattr(zone, "name", ""),
                "OCID": getattr(zone, "id", ""),
                "Scope": getattr(zone, "scope", "") or "PRIVATE",
                "Lifecycle": getattr(zone, "lifecycle_state", ""),
                "Resolution Mode": getattr(zone, "resolution_mode", "") or "",
                "Zone Type": getattr(zone, "zone_type", "") or "",
                "Private View OCID": view_id,
                "Private View Name": view_names.get(view_id, ""),
                "Associated VCNs": ", ".join(view_to_vcns.get(view_id, [])),
            })
        return rows

    def _collect_zone_records(self, compartment_id: str) -> list[dict[str, Any]]:
        """Enumerate DNS records inside every zone (public and private).

        One inventory row per RRSet item, matching the flat row model used by
        the rest of the workbook. Read-only via `get_zone_records`.
        """
        rows: list[dict[str, Any]] = []

        scope_configs = [
            {"scope": None, "resource_type": "DNS Record"},
            {"scope": "PRIVATE", "resource_type": "Private DNS Record"},
        ]

        for cfg in scope_configs:
            list_kwargs: dict[str, Any] = {"compartment_id": compartment_id}
            if cfg["scope"]:
                list_kwargs["scope"] = cfg["scope"]
            try:
                zones = self._paginate(self.manager.dns_client.list_zones, **list_kwargs)
            except Exception as exc:
                logger.warning(
                    "Unable to enumerate zones for scope=%s: %s", cfg["scope"], exc
                )
                zones = []

            for zone in zones:
                zone_id = getattr(zone, "id", "")
                zone_name = getattr(zone, "name", "")
                view_id = getattr(zone, "view_id", "") or ""
                get_kwargs: dict[str, Any] = {"zone_name_or_id": zone_id}
                if cfg["scope"]:
                    get_kwargs["scope"] = cfg["scope"]
                if view_id:
                    get_kwargs["view_id"] = view_id
                try:
                    records = self._paginate(
                        self.manager.dns_client.get_zone_records, **get_kwargs
                    )
                except Exception as exc:
                    logger.warning(
                        "Unable to enumerate DNS records for zone %s: %s", zone_id, exc
                    )
                    records = []
                for record in records:
                    rows.append({
                        "Resource Type": cfg["resource_type"],
                        "Name": getattr(record, "domain", ""),
                        "OCID": zone_id,
                        "Zone Name": zone_name,
                        "Domain": getattr(record, "domain", ""),
                        "RType": getattr(record, "rtype", ""),
                        "TTL": getattr(record, "ttl", ""),
                        "RData": getattr(record, "rdata", "") or "",
                        "Is Protected": getattr(record, "is_protected", ""),
                    })
        return rows

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, 'data') else []
        except Exception as exc:
            logger.warning("Failed to paginate '%s': %s", getattr(list_method, "__name__", str(list_method)), exc)
            return []
