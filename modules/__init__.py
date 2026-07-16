"""
OCI Inventory Generator

Modules Package

This package contains all inventory collectors used by
the OCI Inventory Generator.

All modules are READ ONLY and use OCI LIST/GET APIs only.
"""

__version__ = "1.0.0"

__author__ = "Sanjay Jakhar"

__all__ = [
    "clients",
    "compute",
    "database",
    "network",
    "vpn",
    "loadbalancer",
    "storage",
    "dns",
    "waf",
    "policy",
    "excel",
    "utils"
]
