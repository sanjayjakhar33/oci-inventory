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


# OCI Inventory Generator

A **read-only OCI Inventory Generator** built using the Oracle Cloud Infrastructure (OCI) Python SDK.

This tool inventories an OCI compartment and exports the complete infrastructure inventory into a formatted Excel workbook.

**No resources are created, modified, or deleted.**

---

# Features

Collects inventory for:

- Compute Instances
- VNICs
- Private/Public IPs
- Network Security Groups (NSGs)
- VCNs
- Subnets
- Route Tables
- Security Lists
- Internet Gateways
- NAT Gateways
- Service Gateways
- DRGs
- DRG Attachments
- Remote Peering Connections
- Local Peering Gateways
- DB Systems
- Load Balancers
- Buckets
- Block Volumes
- Boot Volumes
- WAF Policies
- DNS Zones
- IPSec VPNs
- CPEs
- IAM Policies

Exports everything into a single Excel workbook with separate worksheets.

---

# Safety

This project is **100% Read Only**.

It only uses OCI SDK **GET** and **LIST** APIs.

No changes are made to your OCI tenancy.

No resource creation.

No deletion.

No updates.

Safe to execute against Production environments (with read-only permissions).

---

# Requirements

- OCI Cloud Shell (Recommended)
- Python 3.9+
- OCI CLI (already available in Cloud Shell)
- OCI SDK

---

# Repository

Clone the repository:

```bash
git clone https://github.com/sanjayjakhar33/oci-inventory.git
```

Enter the directory:

```bash
cd oci-inventory
```

---

# Install Dependencies

Install Python dependencies.

```bash
pip3 install -r requirements.txt
```

---

# Verify OCI Authentication

Cloud Shell is automatically authenticated.

Verify by running:

```bash
oci os ns get
```

Expected output:

```json
{
  "data": "<namespace>"
}
```

If this works, authentication is successful.

---

# Verify Region

Check the active OCI region.

```bash
echo $OCI_REGION
```

or

```bash
oci iam region list
```

---

# Run the Inventory Tool

Execute:

```bash
python3 main.py
```

---

# Provide Input

The tool will prompt for:

```
Compartment Name:
```

Example

```
Ambajogai
```

Next

```
Compartment OCID:
```

Example

```
ocid1.compartment.oc1..xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Next

```
Region
```

Example

```
ap-hyderabad-1
```

Leave blank to use the current Cloud Shell region (if supported).

---

# Inventory Collection

The tool will collect information for:

```
Compute

Database

Networking

Storage

Load Balancer

VPN

DNS

WAF

Policies
```

Progress is displayed while collecting resources.

Example:

```
Collecting Compute...

Collecting Database...

Collecting Networking...

Collecting VPN...

Collecting Storage...

Collecting DNS...

Collecting WAF...

Generating Excel...

Completed Successfully.
```

---

# Output

The generated workbook will be created inside:

```
output/
```

Example

```
output/

OCI_Inventory_Ambajogai.xlsx
```

---

# Download the Excel File

List generated files.

```bash
ls -lh output
```

Use the OCI Cloud Shell File Browser to download:

```
output/OCI_Inventory_<Compartment>.xlsx
```

---

# Validate Python Files (Optional)

Check for syntax errors.

```bash
python3 -m py_compile main.py
```

Validate all Python files.

```bash
find . -name "*.py" -exec python3 -m py_compile {} \;
```

No output means all files compiled successfully.

---

# Typical Execution Flow

```text
Open OCI Cloud Shell
        │
        ▼
Clone Repository
        │
        ▼
Install Requirements
        │
        ▼
Run main.py
        │
        ▼
Enter Compartment Name
        │
        ▼
Enter Compartment OCID
        │
        ▼
Enter Region
        │
        ▼
Collect OCI Inventory
        │
        ▼
Generate Excel Workbook
        │
        ▼
Download Excel File
```

---

# Example

```bash
git clone https://github.com/sanjayjakhar33/oci-inventory.git

cd oci-inventory

pip3 install -r requirements.txt

python3 main.py
```

Example Input

```
Compartment Name

Ambajogai

Compartment OCID

ocid1.compartment.oc1..aaaaaaaavjwd6hbdvyf7fprwpsegwab4s6jhrgqobdxzowj5klpvyfjg5mkq

Region

ap-hyderabad-1
```

---

# Excel Workbook

The generated workbook contains worksheets similar to:

```
Summary

Compute

Database

VCN

Subnets

NSGs

Gateways

DRGs

Remote Peering

Load Balancer

Storage

DNS

WAF

VPN

Policies
```

---

# Troubleshooting

## Authentication Error

Verify Cloud Shell authentication.

```bash
oci os ns get
```

---

## Permission Error

Ensure the executing user has read permissions for the target compartment.

---

## No Resources Found

Verify:

- Correct Compartment OCID
- Correct Region
- Resources exist in the selected compartment

---

## Python Module Error

Reinstall dependencies.

```bash
pip3 install -r requirements.txt
```

---

## Output Not Generated

Verify the output directory exists.

```bash
ls output
```

---

# IAM Permissions

Recommended minimum permissions:

- inspect compartments
- inspect instances
- inspect virtual-network-family
- inspect volume-family
- inspect database-family
- inspect object-family
- inspect load-balancers
- inspect waas-family
- inspect dns
- inspect policies

Read-only access is sufficient.

---

# License

MIT License

---

# Disclaimer

This project is intended for inventory and reporting purposes only.

It performs **read-only** operations against OCI using the Oracle Cloud Infrastructure Python SDK and does **not** modify any OCI resources.
