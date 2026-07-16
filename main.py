from rich.console import Console

from modules.utils import setup_logger
from modules.utils import get_signer
from modules.excel import create_workbook

console = Console()


def main():

    setup_logger()

    console.rule("[green]OCI Inventory Generator")

    compartment_name = input("Compartment Name : ").strip()

    compartment_id = input("Compartment OCID : ").strip()

    config, signer = get_signer()

    workbook = create_workbook()

    console.print("[green]✓ Authentication successful")

    console.print(f"Region : {config['region']}")

    console.print(f"Compartment : {compartment_name}")

    console.print("[yellow]Workbook initialized")

    workbook.save("output/OCI_Inventory.xlsx")

    console.print("[bold green]Done")


if __name__ == "__main__":
    main()
