# Security Policy

## Read-only guarantee

The OCI Inventory Generator is intentionally implemented as a read-only tool.
It uses only OCI Python SDK `GET` and `LIST` APIs. It does not create,
update, delete, attach, detach, start, stop, terminate, or otherwise modify
any OCI resource.

If you find a code path in this repository that could modify an OCI resource
or leak tenancy data outside the local machine, please treat it as a
security issue and report it privately using the process below.

## Supported versions

The `main` branch is actively maintained. Security fixes will land there
first.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Instead, open a
[GitHub Security Advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
against this repository, or contact the maintainer privately with:

- A description of the issue and its potential impact
- Steps to reproduce (with **no** real OCIDs / tenancy IDs / credentials)
- The OCI Python SDK version and Python version you tested against
- Any suggested mitigation

We aim to acknowledge reports within five business days and provide a fix or
mitigation plan within thirty days for confirmed issues.

## Handling of credentials and tenancy data

- The tool reads credentials only from the standard OCI CLI config file
  (`~/.oci/config` or `/etc/oci/config` in Cloud Shell).
- The tool never uploads inventory data anywhere; the workbook is written
  to the local `output/` directory only.
- Never commit real OCIDs, IPs, hostnames, private keys, API keys, or any
  customer data into this repository. See `.gitignore` for the standard
  set of ignored credential files.

## Responsible disclosure

We appreciate coordinated disclosure. Credit will be given in release notes
to reporters who follow this policy, unless anonymity is requested.
