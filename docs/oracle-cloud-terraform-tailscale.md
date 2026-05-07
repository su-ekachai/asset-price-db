# Infrastructure as Code: Oracle Cloud & Tailscale Setup (Terraform)

**Date**: April 22, 2026
**Summary**: This guide outlines how to provision your OHLCV Data Store infrastructure on **Oracle Cloud Always Free Tier** using **Terraform**. This approach ensures best practices through Infrastructure as Code (IaC) and fully automates the installation and authentication of **Tailscale** for zero-trust database access.

> **100% Free Guarantee**: Everything in this guide (Oracle Cloud ARM instance, Tailscale Free tier, and Terraform) is completely free of charge. No paid add-ons are required.

---

## 1. Prerequisites

Before running the Terraform code, ensure you have the following:

### 1.1. Tailscale Auth Key
1. Go to the [Tailscale Admin Console -> Settings -> Keys](https://login.tailscale.com/admin/settings/keys).
2. Click **Generate auth key**.
3. Enable **Reusable** and **Ephemeral** (if you plan to rebuild often).
4. Copy the `tskey-auth-...` string. This allows your VM to join your private network automatically on boot.

### 1.2. Oracle Cloud API Configuration
1. Install the [Oracle Cloud CLI (OCI CLI)](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) and [Terraform](https://developer.hashicorp.com/terraform/downloads).
2. Configure OCI CLI using `oci setup config`. This generates an RSA key pair and provides your **Tenancy OCID**, **User OCID**, and **Fingerprint**.
3. Note your **Compartment OCID** (usually the same as Tenancy OCID for root) and your **Region** (e.g., `us-ashburn-1`).

---

## 2. Terraform Project Structure

Create a directory (e.g., `infra/`) and create the following files.

### 2.1. `provider.tf`
Configures the official OCI provider.

```hcl
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
```

### 2.2. `variables.tf`
Defines the sensitive inputs.

```hcl
variable "tenancy_ocid" {}
variable "user_ocid" {}
variable "fingerprint" {}
variable "private_key_path" {}
variable "region" { default = "us-ashburn-1" }
variable "compartment_ocid" {}

# Tailscale and SSH
variable "ssh_public_key" {
  description = "Public SSH key to access the instance natively as opc/ubuntu user"
}
variable "tailscale_auth_key" {
  description = "Tailscale Auth Key (tskey-auth-...)"
  sensitive   = true
}
```

### 2.3. `network.tf`
Creates a Virtual Cloud Network (VCN) with a restrictive Security List following OCI naming conventions. Database ports are kept private.

```hcl
resource "oci_core_vcn" "ohlcv_prod_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "ohlcv-prod-vcn"
}

resource "oci_core_internet_gateway" "ohlcv_prod_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.ohlcv_prod_vcn.id
  display_name   = "ohlcv-prod-igw"
}

resource "oci_core_default_route_table" "ohlcv_prod_route" {
  manage_default_resource_id = oci_core_vcn.ohlcv_prod_vcn.default_route_table_id
  display_name               = "ohlcv-prod-route"
  route_rules {
    network_entity_id = oci_core_internet_gateway.ohlcv_prod_igw.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

resource "oci_core_default_security_list" "ohlcv_prod_tailscale_sl" {
  manage_default_resource_id = oci_core_vcn.ohlcv_prod_vcn.default_security_list_id
  display_name               = "ohlcv-prod-tailscale-sl"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }
}

resource "oci_core_subnet" "ohlcv_prod_public_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.ohlcv_prod_vcn.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "ohlcv-prod-public-subnet"
  route_table_id    = oci_core_vcn.ohlcv_prod_vcn.default_route_table_id
  security_list_ids = [oci_core_vcn.ohlcv_prod_vcn.default_security_list_id]
}
```

### 2.4. `compute.tf`
Provisions the Always Free ARM instance using the highly optimized `Canonical Ubuntu 24.04 Minimal aarch64` image with `cloud-init` bootstrapping.

```hcl
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

data "oci_core_images" "ubuntu_minimal_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  # Ensure we only fetch the Minimal aarch64 image
  filter {
    name   = "display_name"
    values = ["^Canonical-Ubuntu-24.04-Minimal-aarch64-.*$"]
    regex  = true
  }
}

resource "oci_core_instance" "ohlcv_db_node_1" {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.compartment_ocid
  shape               = "VM.Standard.A1.Flex"
  display_name        = "ohlcv-db-node-1"

  shape_config {
    ocpus         = 4 # Free limit
    memory_in_gbs = 24 # Free limit
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.ohlcv_prod_public_subnet.id
    assign_public_ip = true
    display_name     = "ohlcv-db-node-1-primary-vnic"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_minimal_arm.images[0].id
    boot_volume_size_in_gbs = 50
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
      tailscale_auth_key = var.tailscale_auth_key
    }))
  }
}

output "instance_public_ip" {
  value = oci_core_instance.ohlcv_db_node_1.public_ip
}
```

### 2.5. `cloud-init.yaml`
Automates the zero-touch Tailscale setup.

```yaml
#cloud-config
package_update: true
package_upgrade: true

runcmd:
  # Install Docker
  - curl -fsSL https://get.docker.com -o get-docker.sh
  - sh get-docker.sh
  - usermod -aG docker ubuntu

  # Install and configure Tailscale
  - curl -fsSL https://tailscale.com/install.sh | sh
  - tailscale up --authkey=${tailscale_auth_key} --ssh
```

---

## 3. Deployment Workflow

1. Create a `terraform.tfvars` file and fill in your OCIDs, Region, SSH public key string, and Tailscale Auth Key.
2. Initialize and deploy:
   ```bash
   terraform init
   terraform apply -auto-approve
   ```

---

## 4. Verification

1. Wait ~3 minutes after the command finishes for `cloud-init` to complete.
2. Your server will appear in the **Tailscale Machines** list automatically.
3. Access your server via Tailscale IP (e.g., `100.x.x.x`) without ever using the public IP again.
   ```bash
   ssh ubuntu@<tailscale-ip>
   ```
4. Now you can run your database on the node, and it will be physically inaccessible to anyone not on your Tailscale network.
