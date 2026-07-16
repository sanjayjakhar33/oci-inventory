"""
Compute Inventory Collector

Collects:

- Compute Instances
- Private/Public IP
- NSGs
- Subnet
- VCN
- Boot Volume

READ ONLY
"""

import logging

import oci

from oci.pagination import list_call_get_all_results


class ComputeInventory:

    def __init__(self, clients):

        self.compute = clients.compute

        self.network = clients.network

        self.block = oci.core.BlockstorageClient(clients.config)

        self.identity = clients.identity

        self.logger = logging.getLogger(__name__)

    ####################################################################
    # PUBLIC METHOD
    ####################################################################

    def collect(self, compartment_id):

        self.logger.info("Collecting Compute Inventory")

        inventory = []

        instances = self._list_instances(compartment_id)

        self.logger.info("Found %s instances", len(instances))

        for instance in instances:

            try:

                record = self._build_instance_record(instance)

                inventory.append(record)

            except Exception as ex:

                self.logger.error(
                    "Failed processing %s : %s",
                    instance.display_name,
                    ex
                )

        return inventory

    ####################################################################
    # LIST INSTANCES
    ####################################################################

    def _list_instances(self, compartment_id):

        response = list_call_get_all_results(
            self.compute.list_instances,
            compartment_id=compartment_id
        )

        return response.data

    ####################################################################
    # BUILD COMPLETE RECORD
    ####################################################################

    def _build_instance_record(self, instance):

        private_ip = ""

        public_ip = ""

        subnet_name = ""

        subnet_ocid = ""

        vcn_name = ""

        vcn_ocid = ""

        nsg_names = []

        nsg_ocids = []

        boot_volume = ""

        boot_volume_size = ""

        (
            private_ip,
            public_ip,
            subnet_name,
            subnet_ocid,
            vcn_name,
            vcn_ocid,
            nsg_names,
            nsg_ocids
        ) = self._network_information(instance)

        (
            boot_volume,
            boot_volume_size
        ) = self._boot_volume(instance)

        return {

            "Instance Name": instance.display_name,

            "Instance OCID": instance.id,

            "Lifecycle": instance.lifecycle_state,

            "Shape": instance.shape,

            "Availability Domain":
                instance.availability_domain,

            "Fault Domain":
                instance.fault_domain,

            "Private IP":
                private_ip,

            "Public IP":
                public_ip,

            "Subnet":
                subnet_name,

            "Subnet OCID":
                subnet_ocid,

            "VCN":
                vcn_name,

            "VCN OCID":
                vcn_ocid,

            "NSG":
                ",".join(nsg_names),

            "NSG OCID":
                ",".join(nsg_ocids),

            "Boot Volume":
                boot_volume,

            "Boot Volume Size":
                boot_volume_size,

            "Image OCID":
                instance.image_id,

            "Created":
                str(instance.time_created),

            "Freeform Tags":
                str(instance.freeform_tags),

            "Defined Tags":
                str(instance.defined_tags)

        }
            ####################################################################
    # NETWORK INFORMATION
    ####################################################################

    def _network_information(self, instance):

        private_ip = ""
        public_ip = ""

        subnet_name = ""
        subnet_ocid = ""

        vcn_name = ""
        vcn_ocid = ""

        nsg_names = []
        nsg_ocids = []

        # Get all VNIC Attachments
        attachments = list_call_get_all_results(
            self.compute.list_vnic_attachments,
            compartment_id=instance.compartment_id,
            instance_id=instance.id
        ).data

        if not attachments:

            return (
                private_ip,
                public_ip,
                subnet_name,
                subnet_ocid,
                vcn_name,
                vcn_ocid,
                nsg_names,
                nsg_ocids
            )

        #
        # Usually an instance has one primary VNIC.
        # If multiple exist, we collect all NSGs
        # and keep the first IPs.
        #

        for attachment in attachments:

            vnic = self.network.get_vnic(
                attachment.vnic_id
            ).data

            #
            # Private IP
            #

            if not private_ip:
                private_ip = vnic.private_ip

            #
            # Public IP
            #

            if vnic.public_ip and not public_ip:
                public_ip = vnic.public_ip

            #
            # NSGs
            #

            if vnic.nsg_ids:

                for nsg_id in vnic.nsg_ids:

                    try:

                        nsg = self.network.get_network_security_group(
                            nsg_id
                        ).data

                        nsg_names.append(
                            nsg.display_name
                        )

                        nsg_ocids.append(
                            nsg.id
                        )

                    except Exception as ex:

                        self.logger.warning(
                            "Unable to read NSG %s : %s",
                            nsg_id,
                            ex
                        )

            #
            # Subnet
            #

            subnet = self.network.get_subnet(
                vnic.subnet_id
            ).data

            subnet_name = subnet.display_name
            subnet_ocid = subnet.id

            #
            # VCN
            #

            vcn = self.network.get_vcn(
                subnet.vcn_id
            ).data

            vcn_name = vcn.display_name
            vcn_ocid = vcn.id

        #
        # Remove duplicate NSGs
        #

        nsg_names = list(dict.fromkeys(nsg_names))
        nsg_ocids = list(dict.fromkeys(nsg_ocids))

        return (

            private_ip,

            public_ip,

            subnet_name,

            subnet_ocid,

            vcn_name,

            vcn_ocid,

            nsg_names,

            nsg_ocids

        )
            ####################################################################
    # BOOT VOLUME INFORMATION
    ####################################################################

    def _boot_volume(self, instance):

        boot_volume_name = ""
        boot_volume_size = ""

        try:

            attachments = list_call_get_all_results(
                self.compute.list_boot_volume_attachments,
                availability_domain=instance.availability_domain,
                compartment_id=instance.compartment_id,
                instance_id=instance.id
            ).data

            if not attachments:

                return "", ""

            attachment = attachments[0]

            boot_volume = self.block.get_boot_volume(
                attachment.boot_volume_id
            ).data

            boot_volume_name = boot_volume.display_name

            boot_volume_size = boot_volume.size_in_gbs

        except Exception as ex:

            self.logger.warning(
                "Unable to fetch boot volume for %s : %s",
                instance.display_name,
                ex
            )

        return (
            boot_volume_name,
            boot_volume_size
        )

    ####################################################################
    # EXPORT
    ####################################################################

    def get_inventory(self, compartment_id):

        return self.collect(compartment_id)
