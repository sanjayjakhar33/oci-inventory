# OCI Inventory

OCI Inventory is a read-only Python utility that inventories Oracle Cloud Infrastructure (OCI) resources for a target compartment and exports the result to an Excel workbook.

The tool is designed to run in OCI Cloud Shell and other OCI-compatible environments with a valid OCI CLI configuration profile. It uses only read-only OCI SDK GET/LIST APIs and never performs Create, Update, Delete, or Action operations.

## Features

- Interactive entrypoint with compartment, region, and output directory prompts
- Read-only inventory collection across compute, database, networking, VPN, load balancer, storage, DNS, WAF, and IAM resources
- Workbook export in the form `OCI_Inventory_<Compartment>.xlsx`
- Progress reporting, logging, and resilient error handling per collector
- Modular resource collectors that keep the existing architecture intact

## Prerequisites

Before running the tool, ensure that:

- Python 3.11+ is installed
- Access to an OCI tenancy is available
- Your OCI CLI profile exists in `~/.oci/config`
- Your OCI profile has permission to read the target compartment and its resources

## Cloud Shell setup

In OCI Cloud Shell:

```bash
git clone <repo-url>
cd oci-inventory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

The application will automatically use the default OCI CLI profile from Cloud Shell unless you override it with environment variables:

- `OCI_CLI_PROFILE` or `OCI_PROFILE`
- `OCI_REGION`
- `OCI_CONFIG_FILE`
- `OCI_COMPARTMENT_NAME`
- `OCI_COMPARTMENT_OCID`
- `OCI_OUTPUT_DIR`

## Installation

```bash
cd oci-inventory
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Interactive mode:

```bash
python3 main.py
```

You will be prompted for:

- Compartment Name
- Compartment OCID
- Region (optional; defaults to the OCI profile region if available)
- Output directory (defaults to `./output`)

Non-interactive mode:

```bash
export OCI_COMPARTMENT_NAME="my-compartment"
export OCI_COMPARTMENT_OCID="ocid1.compartment.oc1..example"
export OCI_REGION="us-ashburn-1"
export OCI_OUTPUT_DIR="./output"
python3 main.py
```

## Sample output

A typical run generates a workbook named like:

```text
output/OCI_Inventory_my-compartment.xlsx
```

The workbook contains:

- Summary sheet
- Separate sheets per resource type
- Frozen header row
- Auto filters
- Auto-sized columns
- Bold headers
- Empty sheets when a collector returns no data

## Troubleshooting

If the tool fails to start:

1. Confirm that `~/.oci/config` exists in Cloud Shell.
2. Confirm that the active profile name is reachable through `OCI_CLI_PROFILE` or `OCI_PROFILE`.
3. Confirm that the compartment OCID and region are correct.
4. Review `logs/oci_inventory.log` for collector-level errors.

If collectors return empty results:

- Verify the profile has access to the target compartment.
- Confirm that the target region is correct.
- Confirm that the resources exist in the compartment.

## Required IAM permissions (read-only)

The tool must be run with a user, instance principal, or resource principal that has read-only access to the target compartment and the OCI services you want to inventory.

Minimum read-only permissions commonly required:

- `read` access to Compartments
- `read` access to Compute instances and VNICs
- `read` access to Networking resources such as VCNs, subnets, DRGs, NSGs, route tables, and public/private IPs
- `read` access to Database services and DB systems
- `read` access to Load Balancers, Buckets, Block Volumes, WAF, DNS, and IAM policy resources

A policy similar to the following is typically sufficient for a scoped read-only inventory workflow:

```text
Allow group <group-name> to inspect compartments in compartment <target-compartment>
Allow group <group-name> to read instances in compartment <target-compartment>
Allow group <group-name> to read vnics in compartment <target-compartment>
Allow group <group-name> to read vcn-family in compartment <target-compartment>
Allow group <group-name> to read db-family in compartment <target-compartment>
Allow group <group-name> to read load-balancer-family in compartment <target-compartment>
Allow group <group-name> to read object-family in compartment <target-compartment>
Allow group <group-name> to read dns in compartment <target-compartment>
Allow group <group-name> to read waas-family in compartment <target-compartment>
Allow group <group-name> to read iam in compartment <target-compartment>
```

## Safety statement

This repository is intentionally implemented as a read-only inventory tool. It uses OCI SDK `GET` and `LIST` APIs only. No OCI Create, Update, Delete, or Action APIs are used anywhere in the repository.
