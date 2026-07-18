# Contributing

Thanks for your interest in improving the OCI Inventory Generator!

## Ground rules

- The tool is **strictly read-only**. Every contribution MUST use only OCI
  SDK `GET` / `LIST` APIs. Pull requests that introduce `create_*`,
  `update_*`, `delete_*`, `attach_*`, `detach_*`, `terminate_*`, `start_*`,
  `stop_*`, `change_*`, or any other mutating call will not be accepted.
- No telemetry, analytics, or outbound network calls other than the
  authenticated OCI SDK request required to inventory the target compartment.
- Do not commit tenancy IDs, OCIDs, IPs, hostnames, credentials, or any
  customer-identifying data. Placeholder values are fine
  (e.g. `ocid1.compartment.oc1..<REDACTED>`).

## Getting started

1. Fork the repository and create a feature branch.
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Make your changes. Preserve the existing workbook structure — sheet
   names, column headers, and row formatting are considered a stable
   public interface.
4. Run the smoke tests:
   ```bash
   python3 tests/test_collectors_smoke.py
   ```
5. If you add a new collector or SDK call, add or extend the smoke test to
   cover it.

## Pull request checklist

- [ ] Only `GET` / `LIST` OCI SDK APIs are used.
- [ ] Every OCI SDK call is wrapped in exception handling and continues on
      failure with a warning log.
- [ ] Every paginated OCI list call uses `list_call_get_all_results`.
- [ ] Workbook sheet names and column headers are unchanged (or the change
      is called out explicitly in the PR description).
- [ ] No customer or tenancy data has been committed.
- [ ] `python3 -m py_compile` passes on all touched files.
- [ ] `python3 tests/test_collectors_smoke.py` passes locally.

## Reporting bugs

Please open a GitHub issue with:

- OCI region and (redacted) resource types affected
- Full traceback and any relevant `logs/oci_inventory.log` excerpts
- OCI Python SDK version (`pip show oci`)
- Python version (`python3 --version`)

## Code style

The project uses standard `black`-compatible formatting. Keep functions
focused, add type hints where practical, and prefer small, targeted changes
over broad refactors.
