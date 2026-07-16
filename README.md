# OCI Inventory

A Python-based inventory tool for collecting and exporting Oracle Cloud Infrastructure (OCI) resource data.

## Project structure

- `main.py` – entry point
- `config.py` – configuration and environment settings
- `modules/` – resource-specific collectors
- `output/` – generated reports
- `logs/` – runtime logs

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```
