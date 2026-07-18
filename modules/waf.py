"""WAF inventory collector.

Covers both:
- Legacy WAAS policies (`oci.waas.WaasClient`)
- Modern WAF (v2) Web Application Firewalls and Policies
  (`oci.waf.WafClient`)

Every child resource (protection rule, access rule, address list, caching
rule, whitelist, custom protection rule, captcha, JS/device fingerprint /
human interaction challenge, rate limiting, request/response access control)
is emitted as a dedicated inventory row instead of being embedded as JSON.
"""

from __future__ import annotations

import logging
from typing import Any

from oci.pagination import list_call_get_all_results

from modules.utils import InventoryCache

logger = logging.getLogger(__name__)


class WAFCollector:
    """Collect OCI WAF / WAAS inventory for a compartment."""

    def __init__(self, manager: Any, cache: InventoryCache) -> None:
        self.manager = manager
        self.cache = cache

    def collect(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._collect_waas_policies(compartment_id))
        rows.extend(self._collect_waas_certificates(compartment_id))
        rows.extend(self._collect_waas_custom_protection_rules(compartment_id))
        rows.extend(self._collect_waf_v2(compartment_id))
        # Additive: unified "WAF Access Rule" rows with the schema documented
        # in the requirements (Policy Name / WAF Name / Rule Name / Action /
        # Priority / State / Condition / Description). Existing rows above
        # remain unchanged.
        rows.extend(self._collect_access_rules_flat(compartment_id))
        return rows

    # -----------------------------------------------------------------
    # Legacy WAAS (Edge policies)
    # -----------------------------------------------------------------

    def _collect_waas_policies(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for policy in self._paginate(
            self.manager.waas_client.list_waas_policies, compartment_id=compartment_id
        ):
            policy_id = getattr(policy, "id", "")
            policy_name = getattr(policy, "display_name", "")
            domain_name = getattr(policy, "domain", "") or ""
            additional_domains = getattr(policy, "additional_domains", []) or []

            base_row = {
                "Resource Type": "WAAS Policy",
                "Name": policy_name,
                "OCID": policy_id,
                "Frontend Hostname": domain_name,
                "Additional Domains": ", ".join(additional_domains),
                "CNAME": getattr(policy, "cname", "") or "",
                "Compartment": getattr(policy, "compartment_id", "") or "",
                "Lifecycle": getattr(policy, "lifecycle_state", ""),
            }
            try:
                details = self.manager.waas_client.get_waas_policy(waas_policy_id=policy_id).data
                origins = ", ".join((getattr(details, "origins", {}) or {}).keys())
                base_row["Origins"] = origins
                base_row["CNAME"] = getattr(details, "cname", "") or base_row["CNAME"]
                base_row["Additional Domains"] = ", ".join(
                    getattr(details, "additional_domains", []) or additional_domains
                )
            except Exception as exc:
                logger.warning("Unable to enrich WAAS policy %s: %s", policy_id, exc)
            rows.append(base_row)

            rows.extend(self._collect_waas_child_rules(policy_id, policy_name))
        return rows

    def _collect_waas_child_rules(self, policy_id: str, policy_name: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for rule in self._paginate(
            self.manager.waas_client.list_protection_rules, waas_policy_id=policy_id
        ):
            rows.append({
                "Resource Type": "WAAS Protection Rule",
                "Name": getattr(rule, "name", "") or getattr(rule, "key", ""),
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Rule Key": getattr(rule, "key", ""),
                "Action": getattr(rule, "action", ""),
                "Mod Security Rule IDs": ", ".join(getattr(rule, "mod_security_rule_ids", []) or []),
                "Description": getattr(rule, "description", "") or "",
            })

        for rule in self._paginate(
            self.manager.waas_client.list_access_rules, waas_policy_id=policy_id
        ):
            rows.append({
                "Resource Type": "WAAS Access Rule",
                "Name": getattr(rule, "name", ""),
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Action": getattr(rule, "action", ""),
                "Block Action": getattr(rule, "block_action", "") or "",
                "Block Response Code": getattr(rule, "block_response_code", "") or "",
                "Bypass Challenges": ", ".join(getattr(rule, "bypass_challenges", []) or []),
                "Criteria": str(getattr(rule, "criteria", "") or ""),
            })

        for rule in self._paginate(
            self.manager.waas_client.list_caching_rules, waas_policy_id=policy_id
        ):
            rows.append({
                "Resource Type": "WAAS Caching Rule",
                "Name": getattr(rule, "name", ""),
                "OCID": getattr(rule, "key", "") or policy_id,
                "WAAS Policy": policy_name,
                "Action": getattr(rule, "action", ""),
                "Caching Duration": getattr(rule, "caching_duration", "") or "",
                "Client Caching Duration": getattr(rule, "client_caching_duration", "") or "",
                "Is Client Caching Enabled": getattr(rule, "is_client_caching_enabled", ""),
                "Criteria": str(getattr(rule, "criteria", "") or ""),
            })

        for whitelist in self._paginate(
            self.manager.waas_client.list_whitelists, waas_policy_id=policy_id
        ):
            rows.append({
                "Resource Type": "WAAS Whitelist",
                "Name": getattr(whitelist, "name", ""),
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Addresses": ", ".join(getattr(whitelist, "addresses", []) or []),
                "Address Lists": ", ".join(getattr(whitelist, "address_lists", []) or []),
            })

        for captcha in self._paginate(
            self.manager.waas_client.list_captchas, waas_policy_id=policy_id
        ):
            rows.append({
                "Resource Type": "WAAS Captcha",
                "Name": getattr(captcha, "title", "") or getattr(captcha, "url", ""),
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "URL": getattr(captcha, "url", ""),
                "Session Expiration In Seconds": getattr(captcha, "session_expiration_in_seconds", ""),
                "Failure Message": getattr(captcha, "failure_message", "") or "",
                "Header Text": getattr(captcha, "header_text", "") or "",
            })

        for rule in self._paginate(
            self.manager.waas_client.list_waas_policy_custom_protection_rules,
            waas_policy_id=policy_id,
        ):
            rows.append({
                "Resource Type": "WAAS Custom Protection Rule (Assigned)",
                "Name": getattr(rule, "display_name", "") or getattr(rule, "id", ""),
                "OCID": getattr(rule, "id", ""),
                "WAAS Policy": policy_name,
                "Action": getattr(rule, "action", ""),
                "Mod Security Rule IDs": ", ".join(getattr(rule, "mod_security_rule_ids", []) or []),
            })

        # Challenges / rate limiting / access control aggregations
        try:
            dfc = self.manager.waas_client.get_device_fingerprint_challenge(
                waas_policy_id=policy_id
            ).data
            rows.append({
                "Resource Type": "WAAS Device Fingerprint Challenge",
                "Name": "device_fingerprint_challenge",
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Is Enabled": getattr(dfc, "is_enabled", ""),
                "Action": getattr(dfc, "action", "") or "",
                "Action Expiration In Seconds": getattr(dfc, "action_expiration_in_seconds", ""),
                "Challenge Settings": str(getattr(dfc, "challenge_settings", "") or ""),
            })
        except Exception as exc:
            logger.warning("Unable to fetch device fingerprint challenge for %s: %s", policy_id, exc)

        try:
            hic = self.manager.waas_client.get_human_interaction_challenge(
                waas_policy_id=policy_id
            ).data
            rows.append({
                "Resource Type": "WAAS Human Interaction Challenge",
                "Name": "human_interaction_challenge",
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Is Enabled": getattr(hic, "is_enabled", ""),
                "Action": getattr(hic, "action", "") or "",
                "Interaction Threshold": getattr(hic, "interaction_threshold", ""),
                "Recording Period In Seconds": getattr(hic, "recording_period_in_seconds", ""),
            })
        except Exception as exc:
            logger.warning("Unable to fetch human interaction challenge for %s: %s", policy_id, exc)

        try:
            js = self.manager.waas_client.get_js_challenge(waas_policy_id=policy_id).data
            rows.append({
                "Resource Type": "WAAS JS Challenge",
                "Name": "js_challenge",
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Is Enabled": getattr(js, "is_enabled", ""),
                "Action": getattr(js, "action", "") or "",
                "Failure Threshold": getattr(js, "failure_threshold", ""),
                "Action Expiration In Seconds": getattr(js, "action_expiration_in_seconds", ""),
            })
        except Exception as exc:
            logger.warning("Unable to fetch JS challenge for %s: %s", policy_id, exc)

        try:
            rl = self.manager.waas_client.get_waf_address_rate_limiting(
                waas_policy_id=policy_id
            ).data
            rows.append({
                "Resource Type": "WAAS Rate Limiting",
                "Name": "address_rate_limiting",
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Is Enabled": getattr(rl, "is_enabled", ""),
                "Allowed Rate Per Address": getattr(rl, "allowed_rate_per_address", ""),
                "Max Delayed Count Per Address": getattr(rl, "max_delayed_count_per_address", ""),
                "Block Response Code": getattr(rl, "block_response_code", ""),
            })
        except Exception as exc:
            logger.warning("Unable to fetch rate limiting for %s: %s", policy_id, exc)

        try:
            settings = self.manager.waas_client.get_protection_settings(
                waas_policy_id=policy_id
            ).data
            rows.append({
                "Resource Type": "WAAS Protection Settings",
                "Name": "protection_settings",
                "OCID": policy_id,
                "WAAS Policy": policy_name,
                "Block Action": getattr(settings, "block_action", "") or "",
                "Block Response Code": getattr(settings, "block_response_code", "") or "",
                "Allowed HTTP Methods": ", ".join(getattr(settings, "allowed_http_methods", []) or []),
                "Max Argument Count": getattr(settings, "max_argument_count", ""),
                "Max Name Length Per Argument": getattr(settings, "max_name_length_per_argument", ""),
                "Max Total Name Length Of Arguments": getattr(settings, "max_total_name_length_of_arguments", ""),
                "Max Response Size In Ki B": getattr(settings, "max_response_size_in_ki_b", ""),
                "Media Types": ", ".join(getattr(settings, "media_types", []) or []),
            })
        except Exception as exc:
            logger.warning("Unable to fetch protection settings for %s: %s", policy_id, exc)

        return rows

    def _collect_waas_certificates(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for certificate in self._paginate(
            self.manager.waas_client.list_certificates, compartment_id=compartment_id
        ):
            rows.append({
                "Resource Type": "WAAS Certificate",
                "Name": getattr(certificate, "display_name", ""),
                "OCID": getattr(certificate, "id", ""),
                "Lifecycle": getattr(certificate, "lifecycle_state", ""),
            })
        return rows

    def _collect_waas_custom_protection_rules(self, compartment_id: str) -> list[dict[str, Any]]:
        rows = []
        for rule in self._paginate(
            self.manager.waas_client.list_custom_protection_rules, compartment_id=compartment_id
        ):
            rows.append({
                "Resource Type": "WAAS Custom Protection Rule",
                "Name": getattr(rule, "display_name", ""),
                "OCID": getattr(rule, "id", ""),
                "Mod Security Rule IDs": ", ".join(getattr(rule, "mod_security_rule_ids", []) or []),
                "Lifecycle": getattr(rule, "lifecycle_state", ""),
                "Description": getattr(rule, "description", "") or "",
            })
        return rows

    # -----------------------------------------------------------------
    # WAF v2 (modern)
    # -----------------------------------------------------------------

    def _collect_waf_v2(self, compartment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for firewall in self._paginate(
            self.manager.waf_client.list_web_app_firewalls, compartment_id=compartment_id
        ):
            fw_id = getattr(firewall, "id", "")
            fw_name = getattr(firewall, "display_name", "")
            policy_id = getattr(firewall, "web_app_firewall_policy_id", "") or ""

            # Fetch full firewall to expose LB association / hostnames if
            # available on the subtype (LB or NLB).
            frontend = ""
            additional_domains: list[str] = []
            try:
                fw_details = self.manager.waf_client.get_web_app_firewall(
                    web_app_firewall_id=fw_id
                ).data
                lb_id = getattr(fw_details, "load_balancer_id", "") or ""
                if lb_id:
                    # Resolve frontend hostname via associated LB hostnames.
                    try:
                        hostnames = self._paginate(
                            self.manager.load_balancer_client.list_hostnames,
                            load_balancer_id=lb_id,
                        )
                        names = [getattr(h, "hostname", "") for h in hostnames if getattr(h, "hostname", "")]
                        if names:
                            frontend = names[0]
                            additional_domains = names[1:]
                    except Exception as exc:
                        logger.warning("Unable to resolve LB hostnames for WAF %s: %s", fw_id, exc)
            except Exception as exc:
                logger.warning("Unable to enrich WAF %s: %s", fw_id, exc)

            rows.append({
                "Resource Type": "WAF Web App Firewall",
                "Name": fw_name,
                "OCID": fw_id,
                "Frontend Hostname": frontend,
                "Additional Domains": ", ".join(additional_domains),
                "Backend Type": getattr(firewall, "backend_type", "") or "",
                "Compartment": getattr(firewall, "compartment_id", "") or "",
                "Policy OCID": policy_id,
                "Lifecycle": getattr(firewall, "lifecycle_state", ""),
            })

        for policy in self._paginate(
            self.manager.waf_client.list_web_app_firewall_policies, compartment_id=compartment_id
        ):
            policy_id = getattr(policy, "id", "")
            policy_name = getattr(policy, "display_name", "")

            rows.append({
                "Resource Type": "WAF Policy",
                "Name": policy_name,
                "OCID": policy_id,
                "Compartment": getattr(policy, "compartment_id", "") or "",
                "Lifecycle": getattr(policy, "lifecycle_state", ""),
            })

            try:
                details = self.manager.waf_client.get_web_app_firewall_policy(
                    web_app_firewall_policy_id=policy_id
                ).data
            except Exception as exc:
                logger.warning("Unable to fetch WAF policy details %s: %s", policy_id, exc)
                continue

            rows.extend(self._collect_waf_v2_actions(policy_id, policy_name, details))
            rows.extend(self._collect_waf_v2_section(
                policy_id, policy_name, "Request Protection", getattr(details, "request_protection", None)
            ))
            rows.extend(self._collect_waf_v2_section(
                policy_id, policy_name, "Response Protection", getattr(details, "response_protection", None)
            ))
            rows.extend(self._collect_waf_v2_access_control(
                policy_id, policy_name, "Request Access Control", getattr(details, "request_access_control", None)
            ))
            rows.extend(self._collect_waf_v2_access_control(
                policy_id, policy_name, "Response Access Control", getattr(details, "response_access_control", None)
            ))
            rows.extend(self._collect_waf_v2_rate_limiting(
                policy_id, policy_name, getattr(details, "request_rate_limiting", None)
            ))

        # Address lists / Protection capabilities (compartment scoped)
        for address_list in self._paginate(
            self.manager.waf_client.list_network_address_lists, compartment_id=compartment_id
        ):
            rows.append({
                "Resource Type": "WAF Network Address List",
                "Name": getattr(address_list, "display_name", ""),
                "OCID": getattr(address_list, "id", ""),
                "Type": getattr(address_list, "type", "") or "",
                "Compartment": getattr(address_list, "compartment_id", "") or "",
                "Lifecycle": getattr(address_list, "lifecycle_state", ""),
            })

        try:
            capabilities = self._paginate(
                self.manager.waf_client.list_protection_capabilities,
                compartment_id=compartment_id,
            )
            for cap in capabilities:
                rows.append({
                    "Resource Type": "WAF Protection Capability",
                    "Name": getattr(cap, "display_name", "") or getattr(cap, "key", ""),
                    "OCID": getattr(cap, "key", ""),
                    "Type": getattr(cap, "type", "") or "",
                    "Version": getattr(cap, "version", "") or "",
                    "Description": getattr(cap, "description", "") or "",
                })
        except Exception as exc:
            logger.warning("Unable to list WAF protection capabilities: %s", exc)

        return rows

    def _collect_waf_v2_actions(
        self, policy_id: str, policy_name: str, details: Any
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for action in getattr(details, "actions", []) or []:
            rows.append({
                "Resource Type": "WAF Policy Action",
                "Name": getattr(action, "name", ""),
                "OCID": policy_id,
                "WAF Policy": policy_name,
                "Type": getattr(action, "type", "") or "",
                "Code": getattr(action, "code", "") or "",
            })
        return rows

    def _collect_waf_v2_section(
        self, policy_id: str, policy_name: str, section_label: str, section: Any
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if section is None:
            return rows
        for rule in getattr(section, "rules", []) or []:
            rows.append({
                "Resource Type": f"WAF {section_label} Rule",
                "Name": getattr(rule, "name", ""),
                "OCID": policy_id,
                "WAF Policy": policy_name,
                "Type": getattr(rule, "type", "") or "",
                "Action Name": getattr(rule, "action_name", "") or "",
                "Condition Language": getattr(rule, "condition_language", "") or "",
                "Condition": getattr(rule, "condition", "") or "",
            })
        body_inspection = getattr(section, "body_inspection_size_limit_in_bytes", None)
        if body_inspection is not None:
            rows.append({
                "Resource Type": f"WAF {section_label} Settings",
                "Name": f"{section_label} Settings",
                "OCID": policy_id,
                "WAF Policy": policy_name,
                "Body Inspection Size Limit Bytes": body_inspection,
                "Body Inspection Size Limit Exceeded Action Name": getattr(
                    section, "body_inspection_size_limit_exceeded_action_name", ""
                ) or "",
            })
        return rows

    def _collect_waf_v2_access_control(
        self, policy_id: str, policy_name: str, section_label: str, section: Any
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if section is None:
            return rows
        for rule in getattr(section, "rules", []) or []:
            rows.append({
                "Resource Type": f"WAF {section_label} Rule",
                "Name": getattr(rule, "name", ""),
                "OCID": policy_id,
                "WAF Policy": policy_name,
                "Type": getattr(rule, "type", "") or "",
                "Action Name": getattr(rule, "action_name", "") or "",
                "Condition Language": getattr(rule, "condition_language", "") or "",
                "Condition": getattr(rule, "condition", "") or "",
            })
        return rows

    def _collect_waf_v2_rate_limiting(
        self, policy_id: str, policy_name: str, section: Any
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if section is None:
            return rows
        for rule in getattr(section, "rules", []) or []:
            configurations = getattr(rule, "configurations", []) or []
            cfg_summary = "; ".join(
                f"period={getattr(c, 'period_in_seconds', '')}s "
                f"limit={getattr(c, 'requests_limit', '')} "
                f"actionDuration={getattr(c, 'action_duration_in_seconds', '')}s"
                for c in configurations
            )
            rows.append({
                "Resource Type": "WAF Rate Limiting Rule",
                "Name": getattr(rule, "name", ""),
                "OCID": policy_id,
                "WAF Policy": policy_name,
                "Type": getattr(rule, "type", "") or "",
                "Action Name": getattr(rule, "action_name", "") or "",
                "Condition Language": getattr(rule, "condition_language", "") or "",
                "Condition": getattr(rule, "condition", "") or "",
                "Configurations": cfg_summary,
            })
        return rows

    # -----------------------------------------------------------------
    # Unified Access Rules (both legacy WAAS and modern WAF v2)
    # -----------------------------------------------------------------

    def _collect_access_rules_flat(self, compartment_id: str) -> list[dict[str, Any]]:
        """Emit one row per Access Rule with the required flat schema.

        Fields: Resource Type, Policy Name, WAF Name, Rule Name, Action,
        Priority, State, Condition, Description.

        Covers OCI WAF v2 (`request_access_control.rules`) and legacy WAAS
        (`list_access_rules`). Existing detailed rows for these entities
        remain in place; this collector is additive.
        """
        rows: list[dict[str, Any]] = []

        # --- Legacy WAAS -------------------------------------------------
        try:
            waas_policies = self._paginate(
                self.manager.waas_client.list_waas_policies,
                compartment_id=compartment_id,
            )
        except Exception as exc:
            logger.warning("Unable to enumerate WAAS policies for access rules: %s", exc)
            waas_policies = []

        for policy in waas_policies:
            policy_id = getattr(policy, "id", "")
            policy_name = getattr(policy, "display_name", "")
            policy_state = getattr(policy, "lifecycle_state", "")
            try:
                access_rules = self._paginate(
                    self.manager.waas_client.list_access_rules,
                    waas_policy_id=policy_id,
                )
            except Exception as exc:
                logger.warning(
                    "Unable to enumerate WAAS access rules for %s: %s", policy_id, exc
                )
                access_rules = []
            for priority, rule in enumerate(access_rules, start=1):
                rows.append({
                    "Resource Type": "WAF Access Rule",
                    "Policy Name": policy_name,
                    "WAF Name": policy_name,
                    "Rule Name": getattr(rule, "name", ""),
                    "Action": getattr(rule, "action", "") or "",
                    "Priority": priority,
                    "State": policy_state,
                    "Condition": str(getattr(rule, "criteria", "") or ""),
                    "Description": "",
                    "OCID": policy_id,
                    "Source": "WAAS",
                })

        # --- WAF v2 ------------------------------------------------------
        # Map policy_id -> WAF Name (first firewall attached to the policy)
        policy_to_waf_name: dict[str, str] = {}
        try:
            firewalls = self._paginate(
                self.manager.waf_client.list_web_app_firewalls,
                compartment_id=compartment_id,
            )
        except Exception as exc:
            logger.warning("Unable to enumerate WAF firewalls for access rules: %s", exc)
            firewalls = []
        for fw in firewalls:
            pid = getattr(fw, "web_app_firewall_policy_id", "") or ""
            if pid and pid not in policy_to_waf_name:
                policy_to_waf_name[pid] = getattr(fw, "display_name", "") or ""

        try:
            v2_policies = self._paginate(
                self.manager.waf_client.list_web_app_firewall_policies,
                compartment_id=compartment_id,
            )
        except Exception as exc:
            logger.warning("Unable to enumerate WAF v2 policies for access rules: %s", exc)
            v2_policies = []

        for policy in v2_policies:
            policy_id = getattr(policy, "id", "")
            policy_name = getattr(policy, "display_name", "")
            policy_state = getattr(policy, "lifecycle_state", "")
            try:
                details = self.manager.waf_client.get_web_app_firewall_policy(
                    web_app_firewall_policy_id=policy_id
                ).data
            except Exception as exc:
                logger.warning(
                    "Unable to fetch WAF v2 policy %s for access rules: %s", policy_id, exc
                )
                continue

            for section_label, section in (
                ("Request", getattr(details, "request_access_control", None)),
                ("Response", getattr(details, "response_access_control", None)),
            ):
                if section is None:
                    continue
                for priority, rule in enumerate(getattr(section, "rules", []) or [], start=1):
                    rows.append({
                        "Resource Type": "WAF Access Rule",
                        "Policy Name": policy_name,
                        "WAF Name": policy_to_waf_name.get(policy_id, ""),
                        "Rule Name": getattr(rule, "name", ""),
                        "Action": getattr(rule, "action_name", "") or "",
                        "Priority": priority,
                        "State": policy_state,
                        "Condition": getattr(rule, "condition", "") or "",
                        "Description": getattr(rule, "type", "") or "",
                        "OCID": policy_id,
                        "Source": f"WAFv2-{section_label}",
                    })

        return rows

    # -----------------------------------------------------------------

    def _paginate(self, list_method: Any, **kwargs: Any) -> list[Any]:
        try:
            response = list_call_get_all_results(list_method, **kwargs)
            return response.data if hasattr(response, "data") else []
        except Exception as exc:
            logger.warning(
                "Failed to paginate '%s': %s",
                getattr(list_method, "__name__", str(list_method)),
                exc,
            )
            return []
