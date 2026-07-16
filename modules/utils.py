import logging
import oci

from config import LOG_FILE


def setup_logger():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def get_signer():
    """
    Cloud Shell uses Resource Principal authentication.
    """
    signer = oci.auth.signers.get_resource_principals_signer()

    config = {
        "region": signer.region
    }

    return config, signer
