# OCI Inventory Generator

A **read-only** command-line tool that inventories Oracle Cloud Infrastructure
(OCI) resources for a target compartment and exports the result to a formatted
Microsoft Excel workbook.

The tool uses only OCI Python SDK `GET` and `LIST` APIs. It **never** performs
Create, Update, Delete, or Action calls, and it is safe to execute against
production tenancies with read-only permissions.

---

## Highlights

- Fully read-only — GET / LIST operations only
- Interactive CLI with compartment, region, and output-directory prompts
- Non-interactive execution via environment variables (CI / Cloud Shell)
- Per-collector progress reporting and resilient error handling
- Modular collectors for Compute, Database, Networking, VPN, Load Balancer,
  Storage, DNS, WAF (WAAS + WAF v2), and IAM Policies
- Excel workbook with a Summary sheet, resource-type sheets, frozen headers,
  auto filters, auto-sized columns, and bold headers
- Automatic detection of the OCI Cloud Shell config profile

## Inventoried resources

The tool collects, without modification, the following resource families:

- Compute Instances, VNIC Attachments, Boot Volume Attachments
- VNICs, Private / Public IPs
- VCNs, Subnets, DHCP Options
- Internet / NAT / Service Gateways
- DRGs, DRG Attachments, DRG Route Tables, DRG Route Distributions,
  Remote Peering Connections, Local Peering Gateways
- Route Tables + Route Rules
- Security Lists + Ingress/Egress Rules
- Network Security Groups + Security Rules
- IPSec VPN Connections + Tunnels, CPEs
- Load Balancers, Backend Sets, Backends, Certificates, Hostnames
- Object Storage Buckets
- Block Volumes, Boot Volumes, Volume Groups, Volume Backups,
  Volume Group Backups
- DB Systems, DB Homes, Databases, DB Nodes
- Cloud VM Clusters, Cloud Exadata Infrastructures
- Autonomous Databases
- DNS Zones, Views, Resolvers
- WAAS Policies + Protection / Access / Caching / Whitelists / Captchas /
  Custom Protection Rules / Device Fingerprint / Human Interaction /
  JS Challenges / Rate Limiting / Protection Settings
- WAF v2 Web App Firewalls + Policies + Actions + Protection Rules +
  Access Control Rules + Rate Limiting Rules + Network Address Lists +
  Protection Capabilities
- IAM Policies

Every child resource is emitted as a dedicated inventory row (not embedded
JSON) so the workbook remains machine-readable.

## Requirements

- Python 3.11+ (Python 3.9+ typically works, but 3.11 is recommended)
- A valid OCI CLI configuration profile at `~/.oci/config`, or execution
  inside OCI Cloud Shell (auto-detected via `/etc/oci/config`)
- Read-only IAM permissions on the target compartment (see below)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Interactive

```bash
python3 main.py
```

You will be prompted for:

- Compartment Name
- Compartment OCID
- Region (optional; defaults to the OCI profile region if available)
- Output directory (defaults to `./output`)

### Non-interactive

```bash
export OCI_COMPARTMENT_NAME="my-compartment"
export OCI_COMPARTMENT_OCID="ocid1.compartment.oc1..<REDACTED>"
export OCI_REGION="us-ashburn-1"
export OCI_OUTPUT_DIR="./output"
python3 main.py
```

Additional overrides:

- `OCI_CLI_PROFILE` / `OCI_PROFILE` — profile name in `~/.oci/config`
- `OCI_CONFIG_FILE` — alternate path to the OCI config file

## Cloud Shell

Cloud Shell is authenticated automatically. You can verify with:

```bash
oci os ns get
```

Then clone and run:

```bash
git clone <your-repo-url>
cd oci-inventory
pip3 install -r requirements.txt
python3 main.py
```

## Output

The workbook is written to `<output_dir>/OCI_Inventory_<Compartment>.xlsx`
and contains:

- A `Summary` sheet with compartment metadata and row counts per module
- One sheet per resource type (e.g. `Networking - NSG`,
  `WAF - WAF Web App Firewall`) with frozen header row, bold headers,
  auto filter, and auto-sized columns
- Empty sheets when a collector returns no data

## Required IAM permissions (read-only)

The executing principal must have read-only access to the target compartment.
A policy similar to the following is typically sufficient:

```text
Allow group <group-name> to inspect compartments in compartment <target>
Allow group <group-name> to read instances in compartment <target>
Allow group <group-name> to read vnic-attachments in compartment <target>
Allow group <group-name> to read vnics in compartment <target>
Allow group <group-name> to read vcn-family in compartment <target>
Allow group <group-name> to read virtual-network-family in compartment <target>
Allow group <group-name> to read volume-family in compartment <target>
Allow group <group-name> to read db-family in compartment <target>
Allow group <group-name> to read autonomous-database-family in compartment <target>
Allow group <group-name> to read load-balancers in compartment <target>
Allow group <group-name> to read object-family in compartment <target>
Allow group <group-name> to read dns in compartment <target>
Allow group <group-name> to read waas-family in compartment <target>
Allow group <group-name> to read waf-family in compartment <target>
Allow group <group-name> to read policies in compartment <target>
```

## Privacy and safety

- 100% read-only — the tool uses only `GET` and `LIST` OCI SDK APIs.
- No telemetry, no analytics, no outbound uploads, no third-party endpoints.
- All output is written locally to the `output/` directory.
- No credentials, OCIDs, IPs, or tenancy-specific data are stored outside
  the local machine or committed to the repository.

## Troubleshooting

**Authentication error** — verify your Cloud Shell / local CLI profile:

```bash
oci os ns get
```

**Permission error** — confirm the executing user has the read-only IAM
permissions listed above on the target compartment.

**No resources found** — verify the compartment OCID, region, and that the
resources actually exist inside the compartment. Check `logs/oci_inventory.log`
for collector-level warnings; individual failures never abort the run.

**Python module error** — reinstall dependencies:

```bash
pip install -r requirements.txt
```

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` for the workflow and
`CODE_OF_CONDUCT.md` for community expectations. Security issues should be
reported per `SECURITY.md`.

## License

MIT License — see the `LICENSE` file.

## Disclaimer

This project is intended for inventory and reporting purposes only. It
performs read-only operations against OCI using the Oracle Cloud
Infrastructure Python SDK and does **not** modify any OCI resources.
