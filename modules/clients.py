"""Reusable OCI client manager.

This module centralizes all OCI service clients used by the inventory collectors.
The implementation is intentionally read-only and uses the OCI CLI profile from
`~/.oci/config` via the `config` profile and signer flow.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import oci

logger = logging.getLogger(__name__)


class OCIClientManager:
    """Manage and reuse OCI service clients for the inventory workflow."""

    def __init__(self, profile: str = "DEFAULT", config_file: str | None = None, region: str | None = None) -> None:
        self.profile = profile or "DEFAULT"
        self.config_file = str(Path(config_file or "~/.oci/config").expanduser())
        self._config = self._load_config()
        resolved_region = region or self._config.get("region")
        self.region = resolved_region
        self.compute_client = oci.core.ComputeClient(self._config, region=self.region)
        self.virtual_network_client = oci.core.VirtualNetworkClient(self._config, region=self.region)
        self.database_client = oci.database.DatabaseClient(self._config, region=self.region)
        self.blockstorage_client = oci.core.BlockstorageClient(self._config, region=self.region)
        self.load_balancer_client = oci.load_balancer.LoadBalancerClient(self._config, region=self.region)
        self.object_storage_client = oci.object_storage.ObjectStorageClient(self._config, region=self.region)
        self.dns_client = oci.dns.DnsClient(self._config, region=self.region)
        self.identity_client = oci.identity.IdentityClient(self._config, region=self.region)
        self.waas_client = oci.waas.WaasClient(self._config, region=self.region)

    def _load_config(self) -> dict[str, Any]:
        """Load OCI config from the CLI profile."""
        logger.info("Loading OCI config from profile '%s' using %s", self.profile, self.config_file)
        
        config_path = Path(self.config_file).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"OCI config file not found: {self.config_file}")

        return oci.config.from_file(self.config_file, self.profile)

    @property
    def compartment_id(self) -> str | None:
        """Return the configured tenancy compartment as a safe fallback."""
        return self._config.get("tenancy")
