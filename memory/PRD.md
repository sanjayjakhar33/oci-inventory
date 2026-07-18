# OCI Inventory Generator — PRD

## Original problem statement
Review and improve the existing OCI Inventory Generator project while preserving
the read-only architecture, coding style, logging, caching and workbook layout.
Fix NSG rule collection (wrong SDK API), enrich WAF inventory (child resources
+ CNAME + policies), fix DBCS inventory (returning zero rows), and correct all
OCI SDK method signatures.

## Tech stack
- Python 3.11+
- Oracle Cloud Infrastructure Python SDK (`oci>=2.132.0`, currently 2.182.0)
- openpyxl for workbook export
- rich for CLI UX
- Read-only (LIST/GET APIs only)

## Modules
- `modules/clients.py` — Central OCI client manager (adds `waf_client` v2)
- `modules/compute.py`, `modules/database.py`, `modules/network.py`,
  `modules/storage.py`, `modules/vpn.py`, `modules/loadbalancer.py`,
  `modules/dns.py`, `modules/waf.py`, `modules/policy.py`
- `modules/utils.py` — logging + `InventoryCache`
- `modules/excel.py` — workbook builder

## What was implemented in this iteration (2026-01)
- **NSG Rule collection fixed**: replaced `get_network_security_group()` with
  `list_network_security_group_security_rules(network_security_group_id=…)` and
  emit one row per rule including Direction, Protocol, Source, Destination,
  Source/Destination Type, TCP/UDP/ICMP Options, Is Stateless, Description.
- **WAF inventory enhanced**: added modern WAF v2 (`oci.waf.WafClient`)
  collection for Web App Firewalls, Policies, per-policy Actions, Request /
  Response Protection Rules, Request / Response Access Control Rules, Rate
  Limiting Rules (with configurations), Network Address Lists, Protection
  Capabilities. For legacy WAAS: Frontend Hostname, CNAME, Additional Domains,
  Protection Rules, Access Rules, Caching Rules, Whitelists, Captchas, Custom
  Protection Rules (assigned + compartment), Device Fingerprint / Human
  Interaction / JS Challenges, Rate Limiting, Protection Settings — each as a
  dedicated inventory row.
- **DBCS inventory fixed**: `list_db_homes`, `list_db_nodes`, `list_databases`
  now correctly use compartment-scoped calls (SDK requires `compartment_id`).
  Added Cloud VM Clusters, Cloud Exadata Infrastructures and Autonomous
  Databases. Enriched DB System with Hostname, Domain, Private IP (via first
  DB Node VNIC), Subnet / VCN names, NSGs, Fault Domains, License Model,
  Node Count. DB Node rows now include VNIC and resolved Private IP.
- **SDK signature fixes**:
  - `get_route_table(rt_id=…)` (was `route_table_id`)
  - `list_ip_sec_connection_tunnels(ipsc_id=…)` (was `ip_sec_connection_id`)
  - `list_boot_volume_attachments(availability_domain=…, compartment_id=…, instance_id=…)`
    (availability_domain is required)
- **Tests**: `tests/test_collectors_smoke.py` exercises all fixes with
  mocked SDK responses and passes.

## Preserved
- Read-only behavior (LIST / GET only)
- Progress reporting, resilient collector-level warnings
- Existing InventoryCache usage and pagination helper
- Workbook layout, filenames, summary sheet
- Cloud Shell detection

## Backlog / Next Action Items
- P1: Add Exadata Cloud@Customer (`list_vm_clusters`) coverage
- P2: Move legacy WAAS behind a feature flag for tenancies that only use WAF v2
- P2: Enrich Load Balancer with backend health status (still read-only via `get_backend_health`)
