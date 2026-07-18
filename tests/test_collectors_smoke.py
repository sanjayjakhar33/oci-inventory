"""Smoke tests validating the refactored collectors call the SDK with correct
signatures and produce the expected inventory rows. Uses mocks so the tests do
not touch OCI.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

# ensure /app on path
sys.path.insert(0, "/app")

# Monkey-patch OCI pagination helper before importing collectors so that the
# helper simply calls the mocked list method directly.
import oci.pagination

def _fake_list_call_get_all_results(list_method, *args, **kwargs):  # noqa: D401
    return list_method(*args, **kwargs)

oci.pagination.list_call_get_all_results = _fake_list_call_get_all_results
# Also patch the ones already imported into modules (importlib re-import)
import importlib
for mod_name in [
    "modules.compute", "modules.database", "modules.network",
    "modules.storage", "modules.vpn", "modules.waf", "modules.loadbalancer",
    "modules.dns", "modules.policy",
]:
    m = importlib.import_module(mod_name)
    m.list_call_get_all_results = _fake_list_call_get_all_results  # type: ignore[attr-defined]

from modules.compute import ComputeCollector  # noqa: E402
from modules.database import DatabaseCollector  # noqa: E402
from modules.dns import DNSCollector  # noqa: E402
from modules.network import NetworkCollector  # noqa: E402
from modules.utils import InventoryCache  # noqa: E402
from modules.vpn import VPNCollector  # noqa: E402
from modules.waf import WAFCollector  # noqa: E402


def _empty_response(data):
    resp = MagicMock()
    resp.data = data
    return resp


def _mgr_with_mocks():
    mgr = SimpleNamespace(
        compute_client=MagicMock(),
        virtual_network_client=MagicMock(),
        database_client=MagicMock(),
        blockstorage_client=MagicMock(),
        load_balancer_client=MagicMock(),
        object_storage_client=MagicMock(),
        dns_client=MagicMock(),
        identity_client=MagicMock(),
        waas_client=MagicMock(),
        waf_client=MagicMock(),
    )
    # Default: everything returns empty
    for client in (
        mgr.compute_client,
        mgr.virtual_network_client,
        mgr.database_client,
        mgr.blockstorage_client,
        mgr.load_balancer_client,
        mgr.object_storage_client,
        mgr.dns_client,
        mgr.identity_client,
        mgr.waas_client,
        mgr.waf_client,
    ):
        for attr in dir(client):
            if attr.startswith("list_"):
                setattr(client, attr, MagicMock(return_value=_empty_response([])))
    return mgr


def test_network_nsg_rules_use_correct_sdk_call():
    mgr = _mgr_with_mocks()
    nsg = SimpleNamespace(id="ocid1.nsg..x", display_name="nsg-1", vcn_id="ocid1.vcn..v", lifecycle_state="AVAILABLE")
    rule = SimpleNamespace(
        id="rule-1",
        direction="INGRESS",
        protocol="6",
        source="10.0.0.0/16",
        destination=None,
        source_type="CIDR_BLOCK",
        destination_type=None,
        tcp_options=None,
        udp_options=None,
        icmp_options=None,
        is_stateless=False,
        is_valid=True,
        description="allow ssh",
    )
    mgr.virtual_network_client.list_network_security_groups = MagicMock(
        return_value=_empty_response([nsg])
    )
    mgr.virtual_network_client.list_network_security_group_security_rules = MagicMock(
        return_value=_empty_response([rule])
    )
    # Also stub other list_ methods used by NetworkCollector
    for name in [
        "list_vcns", "list_subnets", "list_internet_gateways", "list_nat_gateways",
        "list_service_gateways", "list_drgs", "list_drg_attachments", "list_drg_route_tables",
        "list_drg_route_distributions", "list_remote_peering_connections",
        "list_local_peering_gateways", "list_route_tables", "list_security_lists",
        "list_dhcp_options", "list_private_ips", "list_public_ips",
    ]:
        setattr(mgr.virtual_network_client, name, MagicMock(return_value=_empty_response([])))

    collector = NetworkCollector(mgr, InventoryCache())
    rows = collector.collect("ocid1.compartment..c")

    nsg_rows = [r for r in rows if r["Resource Type"] == "NSG"]
    rule_rows = [r for r in rows if r["Resource Type"] == "NSG Rule"]
    assert len(nsg_rows) == 1, f"Expected 1 NSG, got {len(nsg_rows)}"
    assert len(rule_rows) == 1, f"Expected 1 NSG rule row, got {len(rule_rows)}"
    r = rule_rows[0]
    assert r["Direction"] == "INGRESS"
    assert r["Source"] == "10.0.0.0/16"
    assert r["Source Type"] == "CIDR_BLOCK"
    assert r["NSG Name"] == "nsg-1"
    assert r["NSG OCID"] == "ocid1.nsg..x"
    # Confirm correct SDK method was used
    mgr.virtual_network_client.list_network_security_group_security_rules.assert_called()
    print("[OK] NSG rules use list_network_security_group_security_rules")


def test_network_route_table_uses_rt_id():
    mgr = _mgr_with_mocks()
    rt = SimpleNamespace(id="ocid1.rt..a", display_name="rt", vcn_id="v", lifecycle_state="AVAILABLE")
    mgr.virtual_network_client.list_route_tables = MagicMock(
        return_value=_empty_response([rt])
    )
    rule = SimpleNamespace(destination="0.0.0.0/0", destination_type="CIDR_BLOCK", network_entity_id="igw", description="")
    mgr.virtual_network_client.get_route_table = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(route_rules=[rule]))
    )
    for name in [
        "list_vcns", "list_subnets", "list_internet_gateways", "list_nat_gateways",
        "list_service_gateways", "list_drgs", "list_drg_attachments", "list_drg_route_tables",
        "list_drg_route_distributions", "list_remote_peering_connections",
        "list_local_peering_gateways", "list_security_lists", "list_dhcp_options",
        "list_private_ips", "list_public_ips", "list_network_security_groups",
    ]:
        setattr(mgr.virtual_network_client, name, MagicMock(return_value=_empty_response([])))

    collector = NetworkCollector(mgr, InventoryCache())
    collector.collect("ocid1.compartment..c")

    # Confirm rt_id keyword was used
    args, kwargs = mgr.virtual_network_client.get_route_table.call_args
    assert "rt_id" in kwargs, f"Expected 'rt_id' keyword, got kwargs: {kwargs}"
    print("[OK] Route table uses rt_id parameter")


def test_vpn_tunnels_use_ipsc_id():
    mgr = _mgr_with_mocks()
    conn = SimpleNamespace(id="ocid1.ipsec..1", display_name="c", cpe_id="", drg_id="", customer_bgp_asn=[])
    mgr.virtual_network_client.list_cpes = MagicMock(return_value=_empty_response([]))
    mgr.virtual_network_client.list_ip_sec_connections = MagicMock(return_value=_empty_response([conn]))
    mgr.virtual_network_client.list_ip_sec_connection_tunnels = MagicMock(return_value=_empty_response([]))

    collector = VPNCollector(mgr, InventoryCache())
    collector.collect("ocid1.compartment..c")

    args, kwargs = mgr.virtual_network_client.list_ip_sec_connection_tunnels.call_args
    assert "ipsc_id" in kwargs, f"Expected 'ipsc_id' keyword, got kwargs: {kwargs}"
    print("[OK] IPSec tunnels use ipsc_id parameter")


def test_boot_volume_attachments_pass_availability_domain():
    mgr = _mgr_with_mocks()
    inst = SimpleNamespace(
        id="ocid1.instance..i", display_name="host", availability_domain="AD-1",
        fault_domain="FD-1", lifecycle_state="RUNNING", shape="VM.Standard.E4",
        image_id="", freeform_tags={}, defined_tags={}, time_created=None,
    )
    mgr.compute_client.list_instances = MagicMock(return_value=_empty_response([inst]))
    mgr.compute_client.list_vnic_attachments = MagicMock(return_value=_empty_response([]))
    mgr.compute_client.list_boot_volume_attachments = MagicMock(return_value=_empty_response([]))

    collector = ComputeCollector(mgr, InventoryCache())
    collector.collect("ocid1.compartment..c")

    args, kwargs = mgr.compute_client.list_boot_volume_attachments.call_args
    assert "availability_domain" in kwargs and kwargs["availability_domain"] == "AD-1"
    print("[OK] list_boot_volume_attachments passes availability_domain")


def test_database_uses_compartment_scoped_apis():
    mgr = _mgr_with_mocks()
    db_system = SimpleNamespace(
        id="ocid1.dbsys..1", display_name="dbs", database_edition="EE",
        shape="VM.Standard2.2", lifecycle_state="AVAILABLE", cpu_core_count=2,
        data_storage_size_in_gbs=256, availability_domain="AD-1", fault_domains=["FD-1"],
        subnet_id="ocid1.subnet..s", nsg_ids=[], hostname="db1", node_count=1,
        cluster_name="", domain="", version="19c", license_model="LICENSE_INCLUDED",
        reco_storage_size_in_gb=100, compartment_id="ocid1.compartment..c",
    )
    db_home = SimpleNamespace(
        id="ocid1.dbhome..h", display_name="home", db_system_id="ocid1.dbsys..1",
        db_version="19.0.0.0", lifecycle_state="AVAILABLE", vm_cluster_id="",
        home_type="DB",
    )
    database = SimpleNamespace(
        id="ocid1.database..d", db_name="orcl", db_home_id="ocid1.dbhome..h",
        admin_user_name="admin", lifecycle_state="AVAILABLE",
        character_set="AL32UTF8", ncharacter_set="AL16UTF16",
        db_unique_name="orcl_uniq", pdb_name="PDB1", db_workload="OLTP",
        is_cdb=True, db_system_id="ocid1.dbsys..1", vm_cluster_id="",
    )
    db_node = SimpleNamespace(
        id="ocid1.dbnode..n", hostname="db1", db_system_id="ocid1.dbsys..1",
        lifecycle_state="AVAILABLE", availability_domain="AD-1", fault_domain="FD-1",
        vnic_id="ocid1.vnic..v", backup_vnic_id="", vm_cluster_id="",
    )
    mgr.database_client.list_db_systems = MagicMock(return_value=_empty_response([db_system]))
    mgr.database_client.list_db_homes = MagicMock(return_value=_empty_response([db_home]))
    mgr.database_client.list_databases = MagicMock(return_value=_empty_response([database]))
    mgr.database_client.list_db_nodes = MagicMock(return_value=_empty_response([db_node]))
    mgr.database_client.list_cloud_vm_clusters = MagicMock(return_value=_empty_response([]))
    mgr.database_client.list_cloud_exadata_infrastructures = MagicMock(return_value=_empty_response([]))
    mgr.database_client.list_autonomous_databases = MagicMock(return_value=_empty_response([]))
    mgr.virtual_network_client.get_subnet = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(display_name="sub", vcn_id="ocid1.vcn..v"))
    )
    mgr.virtual_network_client.get_vcn = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(display_name="vcn"))
    )
    mgr.virtual_network_client.get_vnic = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(private_ip="10.0.1.5"))
    )

    collector = DatabaseCollector(mgr, InventoryCache())
    rows = collector.collect("ocid1.compartment..c")

    # Check compartment_id was passed to key list APIs
    _, kwargs_homes = mgr.database_client.list_db_homes.call_args
    assert kwargs_homes.get("compartment_id") == "ocid1.compartment..c"
    _, kwargs_dbs = mgr.database_client.list_databases.call_args
    assert kwargs_dbs.get("compartment_id") == "ocid1.compartment..c"
    # list_db_nodes should be called with compartment_id + db_system_id
    call_args = mgr.database_client.list_db_nodes.call_args
    assert call_args.kwargs.get("compartment_id") == "ocid1.compartment..c"
    assert call_args.kwargs.get("db_system_id") == "ocid1.dbsys..1"

    row_types = {r["Resource Type"] for r in rows}
    assert "DB System" in row_types
    assert "DB Home" in row_types
    assert "Database" in row_types
    assert "DB Node" in row_types

    # Enriched fields
    db_row = [r for r in rows if r["Resource Type"] == "DB System"][0]
    assert db_row["Subnet Name"] == "sub"
    assert db_row["VCN Name"] == "vcn"
    assert db_row["Private IP"] == "10.0.1.5"
    print("[OK] Database collector uses compartment-scoped APIs and enriches network")


def test_waf_collector_emits_child_rows():
    mgr = _mgr_with_mocks()
    # WAAS policy
    waas_policy = SimpleNamespace(
        id="ocid1.waas..p", display_name="waas-p", domain="app.example.com",
        additional_domains=["www.example.com"], cname="cname.oraclecloud.net",
        compartment_id="ocid1.compartment..c", lifecycle_state="ACTIVE",
    )
    waas_policy_details = SimpleNamespace(
        cname="cname.oraclecloud.net", additional_domains=["www.example.com"],
        origins={"origin-1": SimpleNamespace(uri="http://backend")},
    )
    mgr.waas_client.list_waas_policies = MagicMock(return_value=_empty_response([waas_policy]))
    mgr.waas_client.get_waas_policy = MagicMock(return_value=SimpleNamespace(data=waas_policy_details))
    # child rules
    prot = SimpleNamespace(key="pk-1", name="XSS", action="BLOCK", mod_security_rule_ids=["941100"], description="")
    mgr.waas_client.list_protection_rules = MagicMock(return_value=_empty_response([prot]))
    ac = SimpleNamespace(name="ac-1", action="ALLOW", block_action=None, block_response_code=None, bypass_challenges=[], criteria=[])
    mgr.waas_client.list_access_rules = MagicMock(return_value=_empty_response([ac]))
    cr = SimpleNamespace(name="cache-1", key="ck1", action="CACHE", caching_duration="PT1H",
                        client_caching_duration=None, is_client_caching_enabled=False, criteria=[])
    mgr.waas_client.list_caching_rules = MagicMock(return_value=_empty_response([cr]))
    wl = SimpleNamespace(name="wl-1", addresses=["1.1.1.1"], address_lists=[])
    mgr.waas_client.list_whitelists = MagicMock(return_value=_empty_response([wl]))
    capt = SimpleNamespace(title="captcha", url="/login", session_expiration_in_seconds=300,
                           failure_message="fail", header_text="hdr")
    mgr.waas_client.list_captchas = MagicMock(return_value=_empty_response([capt]))
    mgr.waas_client.list_waas_policy_custom_protection_rules = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_custom_protection_rules = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_certificates = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.get_device_fingerprint_challenge = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(
            is_enabled=True, action="DETECT", action_expiration_in_seconds=60, challenge_settings=None
        ))
    )
    mgr.waas_client.get_human_interaction_challenge = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(
            is_enabled=True, action="DETECT", interaction_threshold=3, recording_period_in_seconds=60
        ))
    )
    mgr.waas_client.get_js_challenge = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(
            is_enabled=True, action="DETECT", failure_threshold=5, action_expiration_in_seconds=60
        ))
    )
    mgr.waas_client.get_waf_address_rate_limiting = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(
            is_enabled=True, allowed_rate_per_address=5, max_delayed_count_per_address=10, block_response_code=429
        ))
    )
    mgr.waas_client.get_protection_settings = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(
            block_action="SET_RESPONSE_CODE", block_response_code=403,
            allowed_http_methods=["GET","POST"], max_argument_count=200,
            max_name_length_per_argument=100, max_total_name_length_of_arguments=1000,
            max_response_size_in_ki_b=1024, media_types=["text/html"],
        ))
    )

    # WAF v2 firewall + policy
    fw = SimpleNamespace(
        id="ocid1.waf..f", display_name="waf-fw", backend_type="LOAD_BALANCER",
        compartment_id="ocid1.compartment..c", web_app_firewall_policy_id="ocid1.wafp..p",
        lifecycle_state="ACTIVE",
    )
    fw_details = SimpleNamespace(load_balancer_id="ocid1.lb..1")
    mgr.waf_client.list_web_app_firewalls = MagicMock(return_value=_empty_response([fw]))
    mgr.waf_client.get_web_app_firewall = MagicMock(return_value=SimpleNamespace(data=fw_details))
    mgr.load_balancer_client.list_hostnames = MagicMock(return_value=_empty_response([
        SimpleNamespace(hostname="app.example.com"),
        SimpleNamespace(hostname="www.example.com"),
    ]))

    policy = SimpleNamespace(id="ocid1.wafp..p", display_name="waf-p", compartment_id="ocid1.compartment..c", lifecycle_state="ACTIVE")
    action = SimpleNamespace(name="allow", type="ALLOW", code=None)
    rule = SimpleNamespace(name="rule1", type="PROTECTION", action_name="allow",
                           condition_language="JMESPATH", condition="i_am_condition")
    ac_rule = SimpleNamespace(name="ac1", type="ACCESS_CONTROL", action_name="allow",
                              condition_language="JMESPATH", condition="c")
    rl_config = SimpleNamespace(period_in_seconds=60, requests_limit=100, action_duration_in_seconds=60)
    rl_rule = SimpleNamespace(name="rl1", type="REQUEST_RATE_LIMITING", action_name="allow",
                              condition_language="JMESPATH", condition="c", configurations=[rl_config])
    policy_details = SimpleNamespace(
        actions=[action],
        request_protection=SimpleNamespace(rules=[rule], body_inspection_size_limit_in_bytes=8192,
                                            body_inspection_size_limit_exceeded_action_name="allow"),
        response_protection=SimpleNamespace(rules=[rule]),
        request_access_control=SimpleNamespace(rules=[ac_rule], default_action_name="allow"),
        response_access_control=SimpleNamespace(rules=[ac_rule]),
        request_rate_limiting=SimpleNamespace(rules=[rl_rule]),
    )
    mgr.waf_client.list_web_app_firewall_policies = MagicMock(return_value=_empty_response([policy]))
    mgr.waf_client.get_web_app_firewall_policy = MagicMock(return_value=SimpleNamespace(data=policy_details))
    mgr.waf_client.list_network_address_lists = MagicMock(return_value=_empty_response([
        SimpleNamespace(id="ocid1.nal..n", display_name="nal", type="ADDRESSES",
                        compartment_id="ocid1.compartment..c", lifecycle_state="ACTIVE"),
    ]))
    mgr.waf_client.list_protection_capabilities = MagicMock(return_value=_empty_response([
        SimpleNamespace(key="capkey", display_name="cap", type="REQUEST_PROTECTION_CAPABILITY", version="1", description="d"),
    ]))

    collector = WAFCollector(mgr, InventoryCache())
    rows = collector.collect("ocid1.compartment..c")

    types_found = {r["Resource Type"] for r in rows}
    expected = {
        "WAAS Policy", "WAAS Protection Rule", "WAAS Access Rule", "WAAS Caching Rule",
        "WAAS Whitelist", "WAAS Captcha", "WAAS Device Fingerprint Challenge",
        "WAAS Human Interaction Challenge", "WAAS JS Challenge", "WAAS Rate Limiting",
        "WAAS Protection Settings",
        "WAF Web App Firewall", "WAF Policy", "WAF Policy Action",
        "WAF Request Protection Rule", "WAF Response Protection Rule",
        "WAF Request Access Control Rule", "WAF Response Access Control Rule",
        "WAF Rate Limiting Rule", "WAF Network Address List", "WAF Protection Capability",
    }
    missing = expected - types_found
    assert not missing, f"Missing WAF row types: {missing}\nFound: {sorted(types_found)}"
    waas_row = [r for r in rows if r["Resource Type"] == "WAAS Policy"][0]
    assert waas_row["Frontend Hostname"] == "app.example.com"
    assert "www.example.com" in waas_row["Additional Domains"]
    waf_fw = [r for r in rows if r["Resource Type"] == "WAF Web App Firewall"][0]
    assert waf_fw["Frontend Hostname"] == "app.example.com"
    assert waf_fw["Policy OCID"] == "ocid1.wafp..p"
    print("[OK] WAF collector emits child rows and hostnames")


def test_private_ips_use_subnet_id():
    """list_private_ips must be called with subnet_id, not scope/compartment_id."""
    mgr = _mgr_with_mocks()
    subnet = SimpleNamespace(id="ocid1.subnet..s", vcn_id="ocid1.vcn..v", display_name="sub",
                             cidr_block="10.0.0.0/24", lifecycle_state="AVAILABLE",
                             prohibit_public_ip_on_vnic=False)
    mgr.virtual_network_client.list_subnets = MagicMock(return_value=_empty_response([subnet]))
    ip = SimpleNamespace(display_name="pip", id="ocid1.privateip..p",
                         ip_address="10.0.0.5", subnet_id="ocid1.subnet..s",
                         vcn_id="ocid1.vcn..v")
    mgr.virtual_network_client.list_private_ips = MagicMock(return_value=_empty_response([ip]))
    for name in [
        "list_vcns", "list_internet_gateways", "list_nat_gateways",
        "list_service_gateways", "list_drgs", "list_drg_attachments", "list_drg_route_tables",
        "list_drg_route_distributions", "list_remote_peering_connections",
        "list_local_peering_gateways", "list_route_tables", "list_security_lists",
        "list_dhcp_options", "list_public_ips", "list_network_security_groups",
    ]:
        setattr(mgr.virtual_network_client, name, MagicMock(return_value=_empty_response([])))

    collector = NetworkCollector(mgr, InventoryCache())
    rows = collector.collect("ocid1.compartment..c")
    # Confirm subnet_id was used, and scope/compartment_id were NOT passed
    call = mgr.virtual_network_client.list_private_ips.call_args
    assert "subnet_id" in call.kwargs, f"Expected subnet_id kwarg, got {call.kwargs}"
    assert "scope" not in call.kwargs
    assert "compartment_id" not in call.kwargs
    pip_rows = [r for r in rows if r["Resource Type"] == "Private IP"]
    assert len(pip_rows) == 1 and pip_rows[0]["IP Address"] == "10.0.0.5"
    print("[OK] Private IPs enumerated per subnet_id")


def test_dns_private_zones_and_records():
    """Private DNS zones and DNS records are enumerated additively."""
    mgr = _mgr_with_mocks()
    pub_zone = SimpleNamespace(
        id="ocid1.dns-zone..pub", name="example.com", scope="GLOBAL",
        lifecycle_state="ACTIVE", resolution_mode="", view_id="",
        zone_type="PRIMARY",
    )
    priv_zone = SimpleNamespace(
        id="ocid1.dns-zone..priv", name="internal.example.com", scope="PRIVATE",
        lifecycle_state="ACTIVE", resolution_mode="STANDARD",
        view_id="ocid1.view..v", zone_type="PRIMARY",
    )
    priv_view = SimpleNamespace(
        id="ocid1.view..v", display_name="private-view", scope="PRIVATE",
        lifecycle_state="ACTIVE",
    )
    resolver = SimpleNamespace(
        id="ocid1.resolver..r", display_name="rslv", scope="PRIVATE",
        lifecycle_state="ACTIVE", attached_vcn_id="ocid1.vcn..vv",
        default_view_id="ocid1.view..v",
    )
    resolver_details = SimpleNamespace(
        attached_views=[SimpleNamespace(view_id="ocid1.view..v")],
    )
    record_a = SimpleNamespace(
        domain="host.example.com", rtype="A", ttl=300, rdata="10.0.0.1",
        is_protected=False,
    )
    record_priv = SimpleNamespace(
        domain="db.internal.example.com", rtype="A", ttl=60,
        rdata="10.0.1.5", is_protected=False,
    )

    def _list_zones(**kwargs):
        if kwargs.get("scope") == "PRIVATE":
            return _empty_response([priv_zone])
        return _empty_response([pub_zone])

    def _list_views(**kwargs):
        if kwargs.get("scope") == "PRIVATE":
            return _empty_response([priv_view])
        return _empty_response([])

    def _list_resolvers(**kwargs):
        if kwargs.get("scope") == "PRIVATE":
            return _empty_response([resolver])
        return _empty_response([])

    def _get_zone_records(**kwargs):
        if kwargs.get("scope") == "PRIVATE":
            return _empty_response([record_priv])
        return _empty_response([record_a])

    mgr.dns_client.list_zones = MagicMock(side_effect=_list_zones)
    mgr.dns_client.list_views = MagicMock(side_effect=_list_views)
    mgr.dns_client.list_resolvers = MagicMock(side_effect=_list_resolvers)
    mgr.dns_client.get_zone_records = MagicMock(side_effect=_get_zone_records)
    mgr.dns_client.get_resolver = MagicMock(return_value=SimpleNamespace(data=resolver_details))

    rows = DNSCollector(mgr, InventoryCache()).collect("ocid1.compartment..c")

    types_found = {r["Resource Type"] for r in rows}
    assert "Zone" in types_found
    assert "Private DNS Zone" in types_found
    assert "DNS Record" in types_found
    assert "Private DNS Record" in types_found

    priv = [r for r in rows if r["Resource Type"] == "Private DNS Zone"][0]
    assert priv["Name"] == "internal.example.com"
    assert priv["Private View OCID"] == "ocid1.view..v"
    assert priv["Private View Name"] == "private-view"
    assert priv["Associated VCNs"] == "ocid1.vcn..vv"
    assert priv["Resolution Mode"] == "STANDARD"

    priv_rec = [r for r in rows if r["Resource Type"] == "Private DNS Record"][0]
    assert priv_rec["Domain"] == "db.internal.example.com"
    assert priv_rec["RType"] == "A"
    assert priv_rec["RData"] == "10.0.1.5"

    # get_zone_records was called with scope=PRIVATE for private zone
    seen_scopes = {call.kwargs.get("scope") for call in mgr.dns_client.get_zone_records.call_args_list}
    assert "PRIVATE" in seen_scopes
    print("[OK] DNS private zones + records collected")


def test_waf_access_rules_unified_row():
    """A unified `WAF Access Rule` row with the required schema is emitted."""
    mgr = _mgr_with_mocks()

    # WAAS
    waas_policy = SimpleNamespace(
        id="ocid1.waas..p", display_name="waas-p", domain="app.example.com",
        additional_domains=[], cname="", compartment_id="c", lifecycle_state="ACTIVE",
    )
    waas_details = SimpleNamespace(cname="", additional_domains=[], origins={})
    mgr.waas_client.list_waas_policies = MagicMock(return_value=_empty_response([waas_policy]))
    mgr.waas_client.get_waas_policy = MagicMock(return_value=SimpleNamespace(data=waas_details))
    ac = SimpleNamespace(name="wa-1", action="ALLOW", block_action=None,
                         block_response_code=None, bypass_challenges=[], criteria=[])
    mgr.waas_client.list_access_rules = MagicMock(return_value=_empty_response([ac]))
    mgr.waas_client.list_protection_rules = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_caching_rules = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_whitelists = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_captchas = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_certificates = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_custom_protection_rules = MagicMock(return_value=_empty_response([]))
    mgr.waas_client.list_waas_policy_custom_protection_rules = MagicMock(return_value=_empty_response([]))
    for m in ["get_device_fingerprint_challenge", "get_human_interaction_challenge",
              "get_js_challenge", "get_waf_address_rate_limiting", "get_protection_settings"]:
        setattr(mgr.waas_client, m, MagicMock(side_effect=Exception("skip")))

    # WAF v2
    fw = SimpleNamespace(
        id="ocid1.waf..f", display_name="my-waf", backend_type="LOAD_BALANCER",
        compartment_id="c", web_app_firewall_policy_id="ocid1.wafp..p",
        lifecycle_state="ACTIVE",
    )
    mgr.waf_client.list_web_app_firewalls = MagicMock(return_value=_empty_response([fw]))
    mgr.waf_client.get_web_app_firewall = MagicMock(
        return_value=SimpleNamespace(data=SimpleNamespace(load_balancer_id=""))
    )
    policy = SimpleNamespace(id="ocid1.wafp..p", display_name="waf-policy",
                             compartment_id="c", lifecycle_state="ACTIVE")
    mgr.waf_client.list_web_app_firewall_policies = MagicMock(return_value=_empty_response([policy]))
    ac_rule = SimpleNamespace(name="req-allow", type="ACCESS_CONTROL",
                              action_name="allow", condition_language="JMESPATH",
                              condition="i.startsWith('/api')")
    ac_rule2 = SimpleNamespace(name="resp-deny", type="ACCESS_CONTROL",
                               action_name="deny", condition_language="JMESPATH",
                               condition="i.contains('secret')")
    details = SimpleNamespace(
        actions=[],
        request_protection=None,
        response_protection=None,
        request_access_control=SimpleNamespace(rules=[ac_rule], default_action_name="allow"),
        response_access_control=SimpleNamespace(rules=[ac_rule2]),
        request_rate_limiting=None,
    )
    mgr.waf_client.get_web_app_firewall_policy = MagicMock(return_value=SimpleNamespace(data=details))
    mgr.waf_client.list_network_address_lists = MagicMock(return_value=_empty_response([]))
    mgr.waf_client.list_protection_capabilities = MagicMock(return_value=_empty_response([]))

    rows = WAFCollector(mgr, InventoryCache()).collect("ocid1.compartment..c")
    unified = [r for r in rows if r["Resource Type"] == "WAF Access Rule"]
    assert len(unified) == 3, f"Expected 3 unified access rules, got {len(unified)}: {unified}"
    # Required schema keys
    required_keys = {"Resource Type", "Policy Name", "WAF Name", "Rule Name",
                     "Action", "Priority", "State", "Condition", "Description"}
    for r in unified:
        missing = required_keys - set(r.keys())
        assert not missing, f"Row missing keys {missing}: {r}"
    # WAAS row
    waas_ac = [r for r in unified if r["Source"] == "WAAS"][0]
    assert waas_ac["Rule Name"] == "wa-1"
    assert waas_ac["Action"] == "ALLOW"
    assert waas_ac["Priority"] == 1
    # WAF v2 rows: WAF Name resolved from firewall→policy map
    wafv2_rows = [r for r in unified if r["Source"].startswith("WAFv2-")]
    assert len(wafv2_rows) == 2
    for r in wafv2_rows:
        assert r["WAF Name"] == "my-waf"
        assert r["Policy Name"] == "waf-policy"
    print("[OK] Unified WAF Access Rule rows emitted with required schema")


def test_ipsec_customer_lan_pools():
    """Customer LAN info is consolidated onto the IPSec Connection row.

    The previous separate `IPSec Customer LAN` row type has been removed;
    Customer LAN CIDRs, Routing Type, and Traffic Selectors are now columns
    on the single IPSec Connection row.
    """
    mgr = _mgr_with_mocks()
    mgr.virtual_network_client.list_cpes = MagicMock(return_value=_empty_response([]))
    connection = SimpleNamespace(
        id="ocid1.ipsec..1", display_name="ipsec-1", cpe_id="ocid1.cpe..c",
        drg_id="ocid1.drg..d", customer_bgp_asn=[],
        static_routes=["10.10.0.0/16", "192.168.1.0/24"],
    )
    mgr.virtual_network_client.list_ip_sec_connections = MagicMock(return_value=_empty_response([connection]))
    tunnel_policy = SimpleNamespace(
        id="tunnel-1", display_name="t1", lifecycle_state="AVAILABLE",
        vpn_ip="1.1.1.1", route_tables=None, routing="POLICY",
        encryption_domain_config=SimpleNamespace(
            cpe_traffic_selector=["10.20.0.0/16"],
            oracle_traffic_selector=["10.30.0.0/16"],
        ),
    )
    tunnel_bgp = SimpleNamespace(
        id="tunnel-2", display_name="t2", lifecycle_state="AVAILABLE",
        vpn_ip="2.2.2.2", route_tables=None, routing="BGP",
        encryption_domain_config=None,
    )
    mgr.virtual_network_client.list_ip_sec_connection_tunnels = MagicMock(
        return_value=_empty_response([tunnel_policy, tunnel_bgp])
    )

    rows = VPNCollector(mgr, InventoryCache()).collect("ocid1.compartment..c")

    # Removed sheet: no IPSec Customer LAN rows anymore.
    lan_rows = [r for r in rows if r["Resource Type"] == "IPSec Customer LAN"]
    assert lan_rows == [], f"Unexpected IPSec Customer LAN rows remaining: {lan_rows}"

    # Consolidated: exactly one IPSec Connection row with LAN columns
    conn_rows = [r for r in rows if r["Resource Type"] == "IPSec Connection"]
    assert len(conn_rows) == 1
    conn = conn_rows[0]

    # Customer LAN CIDRs: from static_routes
    cidrs = conn["Customer LAN CIDRs"]
    assert "10.10.0.0/16" in cidrs and "192.168.1.0/24" in cidrs

    # Routing Type: STATIC (from connection static_routes) + POLICY + BGP (from tunnels)
    routing = conn["Routing Type"]
    for expected in ("STATIC", "POLICY", "BGP"):
        assert expected in routing, f"Missing {expected} in routing types: {routing}"

    # Traffic Selectors: only from POLICY tunnel's CPE traffic selectors
    ts = conn["Traffic Selectors"]
    assert "10.20.0.0/16" in ts
    assert "t1" in ts  # prefixed with tunnel name

    # Existing columns preserved
    for k in ("Name", "OCID", "CPE Name", "DRG", "Tunnel Public IPs",
              "Tunnel Status", "Static Routes"):
        assert k in conn, f"missing legacy column {k}"

    print("[OK] IPSec Customer LAN consolidated onto IPSec Connection row")


if __name__ == "__main__":
    test_network_nsg_rules_use_correct_sdk_call()
    test_network_route_table_uses_rt_id()
    test_vpn_tunnels_use_ipsc_id()
    test_boot_volume_attachments_pass_availability_domain()
    test_database_uses_compartment_scoped_apis()
    test_waf_collector_emits_child_rows()
    test_private_ips_use_subnet_id()
    test_dns_private_zones_and_records()
    test_waf_access_rules_unified_row()
    test_ipsec_customer_lan_pools()
    print("\nAll smoke tests passed")
