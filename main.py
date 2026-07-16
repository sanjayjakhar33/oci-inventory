"""OCI inventory generator entrypoint.

This tool is read-only and uses the OCI CLI profile configuration from
`~/.oci/config` to build a Microsoft Excel inventory workbook for a target
compartment.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from config import SETTINGS
from modules.clients import OCIClientManager
from modules.compute import ComputeCollector
from modules.database import DatabaseCollector
from modules.dns import DNSCollector
from modules.excel import ExcelWorkbookBuilder
from modules.loadbalancer import LoadBalancerCollector
from modules.network import NetworkCollector
from modules.policy import PolicyCollector
from modules.storage import StorageCollector
from modules.utils import InventoryCache, setup_logging
from modules.vpn import VPNCollector
from modules.waf import WAFCollector

console = Console()
logger = logging.getLogger(__name__)


def prompt_for_inputs() -> tuple[str, str]:
    """Prompt the user for the target compartment details.

    If environment variables are already present, they are used to avoid
    blocking scripted or automated execution.
    """
    console.print("[bold cyan]OCI Inventory Generator[/bold cyan]")
    compartment_name = os.getenv("OCI_COMPARTMENT_NAME") or Prompt.ask("Compartment Name", default="")
    compartment_ocid = os.getenv("OCI_COMPARTMENT_OCID") or Prompt.ask("Compartment OCID", default="")
    return compartment_name, compartment_ocid


def run_inventory(compartment_name: str, compartment_ocid: str) -> Path:
    """Run all inventory collectors and export the workbook."""
    setup_logging()
    logger.info("Starting OCI inventory for compartment '%s' (%s)", compartment_name, compartment_ocid)

    manager = OCIClientManager(
        profile=SETTINGS["profile"],
        config_file=SETTINGS["config_file"],
        region=SETTINGS["region"],
    )

    cache = InventoryCache()
    builder = ExcelWorkbookBuilder()

    collectors = [
        ("Compute", ComputeCollector(manager, cache)),
        ("Database", DatabaseCollector(manager, cache)),
        ("Networking", NetworkCollector(manager, cache)),
        ("VPN", VPNCollector(manager, cache)),
        ("LoadBalancer", LoadBalancerCollector(manager, cache)),
        ("Storage", StorageCollector(manager, cache)),
        ("DNS", DNSCollector(manager, cache)),
        ("WAF", WAFCollector(manager, cache)),
        ("Policies", PolicyCollector(manager, cache)),
    ]

    workbook_rows: dict[str, list[dict[str, object]]] = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for module_name, collector in collectors:
            task = progress.add_task(f"Collecting {module_name} inventory", total=1)
            try:
                data = collector.collect(compartment_ocid)
                workbook_rows[module_name] = data
                progress.update(task, completed=1)
                console.print(f"[green]✓[/green] {module_name} inventory collected: {len(data)} rows")
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.exception("Collector '%s' failed: %s", module_name, exc)
                console.print(f"[yellow]⚠[/yellow] {module_name} inventory failed: {exc}")
                workbook_rows[module_name] = []
                progress.update(task, completed=1)

    workbook_path = builder.write_workbook(
        workbook_rows=workbook_rows,
        compartment_name=compartment_name,
        compartment_ocid=compartment_ocid,
    )

    console.print(f"[bold green]Workbook created:[/bold green] {workbook_path}")
    summary = {"Compartment Name": compartment_name, "Compartment OCID": compartment_ocid}
    for name, rows in workbook_rows.items():
        summary[f"{name} Rows"] = len(rows)
    console.print("[bold]Summary[/bold]")
    for key, value in summary.items():
        console.print(f"  {key}: {value}")

    return workbook_path


def main() -> None:
    compartment_name, compartment_ocid = prompt_for_inputs()
    run_inventory(compartment_name=compartment_name, compartment_ocid=compartment_ocid)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("[yellow]Inventory cancelled by user.[/yellow]")
    except Exception as exc:  # pragma: no cover - top-level safety net
        logger.exception("Unhandled inventory error: %s", exc)
        console.print(f"[bold red]ERROR:[/bold red] {exc}")
        raise
