# Manual UI Setup: Oracle Cloud & Tailscale (Step-by-Step)

**Date**: April 22, 2026
**Summary**: This document provides a detailed, step-by-step walkthrough for manually provisioning an Always Free Ampere A1 instance on Oracle Cloud Infrastructure (OCI) using the web console UI. It uses Oracle's naming convention best practices and the `Canonical Ubuntu 24.04 Minimal aarch64` OS image to securely host the OHLCV Data Store.

---

## Part 1: Provisioning the Compute Instance (Oracle Cloud UI)

### 1.1. Login and Navigation
1. Log in to your [Oracle Cloud Console](https://cloud.oracle.com).
2. Click the **Hamburger Menu** (top-left) ➡️ **Compute** ➡️ **Instances**.
3. Click the **Create Instance** button.

### 1.2. Name and Compartment
1. **Name**: `ohlcv-db-node-1`
2. **Compartment**: Leave as the default root compartment or select the specific one you want to use.

### 1.3. Image and Shape Selection
Here, we select the most secure, lightweight Always Free ARM architecture.

1. In the **Image and Shape** section, click **Edit**.
2. **Change Image**:
   - Click **Change Image**.
   - Select **Canonical Ubuntu**.
   - **Crucial**: Look for **`Canonical Ubuntu 24.04 Minimal aarch64`**.
   - Click **Select Image**.
3. **Change Shape**:
   - Click **Change Shape**.
   - Select the **Virtual Machine** instance type.
   - Select the **Ampere** shape series.
   - Choose the `VM.Standard.A1.Flex` shape. Check that it has the "Always Free Eligible" tag.
   - Scroll down to **Shape configuration**:
     - **Number of OCPUs**: Slide to `2` (free limit since June 2026).
     - **Amount of Memory (GB)**: Slide to `12` (free limit since June 2026).
   - Click **Select Shape**.

### 1.4. Networking Setup
1. In the **Primary network** section, select **Create new virtual cloud network**.
2. **New VCN Name**: `ohlcv-prod-vcn`.
3. **Subnet**: Select **Create new public subnet**.
4. **New Subnet Name**: `ohlcv-prod-public-subnet`.
5. Ensure **Assign a public IPv4 address** is checked. *(You need a public IP to SSH in for the initial Tailscale setup).*

### 1.5. Advanced Network Configuration (VNIC Name)
1. Click **Show advanced options** under Networking.
2. In the **VNIC name** field, enter: `ohlcv-db-node-1-primary-vnic`.

### 1.6. SSH Keys
1. Under **Add SSH keys**, select **Generate a key pair for me**.
2. Click **Save private key** (e.g., `ssh-key-2026-04-22.key`). **Important**: You must download this now; you cannot retrieve it later.
3. Click **Save public key** as a backup.

### 1.7. Boot Volume
1. In the **Boot volume** section, you can leave the default (50 GB) or specify a custom size up to **200 GB** (the total Always Free block storage limit).
2. Click the final **Create** button at the bottom of the page.
3. Wait for the instance state to change from `PROVISIONING` to `RUNNING`. Note the **Public IP Address** displayed on the instance details page.

---

## Part 2: Configuring the VCN Security List (Firewall)

Oracle Cloud blocks all inbound ports by default except SSH (Port 22). To maintain a zero-trust architecture, we will **NOT** open the QuestDB ports (9000, 8812) to the public internet.

1. On your Instance Details page, click the **Subnet** link (`ohlcv-prod-public-subnet`) in the Instance Information tab.
2. Click on the **Security Lists** link (e.g., `Default Security List for ohlcv-prod-vcn` which you can rename to `ohlcv-prod-tailscale-sl`).
3. Under **Ingress Rules**, ensure there is a rule allowing TCP port `22` (SSH) from `0.0.0.0/0`.
4. **Crucial Step**: Verify that there are NO rules for ports `9000` or `8812`. This guarantees that if anyone tries to scan your public IP, the database is completely invisible.

---

## Part 3: Connecting via SSH & Hardening

1. Open your terminal (Mac/Linux) or PowerShell (Windows).
2. Restrict permissions on your downloaded private key:
   ```bash
   chmod 400 ssh-key-2026-04-22.key
   ```
3. Connect to the instance:
   ```bash
   ssh -i ssh-key-2026-04-22.key ubuntu@<YOUR_PUBLIC_IP>
   ```
4. Once logged in, update the server:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

---

## Part 4: Tailscale Zero-Trust Setup

Tailscale will create a secure, private mesh network allowing your other servers/laptops to connect to the database as if they were on the same local network.

### 4.1. Install Tailscale
1. Run the official install script:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```
2. Authenticate the machine to your Tailnet:
   ```bash
   sudo tailscale up --ssh
   ```
   *(The `--ssh` flag allows you to SSH into this machine over Tailscale without needing the `.key` file in the future).*
3. The terminal will display a URL (e.g., `https://login.tailscale.com/a/xxxxxx`). Copy and paste this URL into your browser and log in to authorize the Oracle VM.

### 4.2. Verify the Tailscale IP
1. Once authenticated, run:
   ```bash
   tailscale ip -4
   ```
2. This will output a private IP address starting with `100.` (e.g., `100.x.x.x`). This is the IP address you will use to connect to QuestDB securely.

---

## Part 5: Deploying the Application

Now that the secure tunnel is up, install Docker and run your application.

### 5.1. Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
# Log out and log back in to apply group changes
exit
```
*Reconnect via SSH (or Tailscale SSH: `tailscale ssh ubuntu@ohlcv-db-node-1`).*

### 5.2. Configure and Run `docker-compose.yml`
Ensure your `docker-compose.yml` binds QuestDB exclusively to the Tailscale IP:

```yaml
services:
  questdb:
    image: questdb/questdb:latest
    ports:
      # Use the Tailscale IP you noted in Step 4.2
      - "100.x.x.x:9000:9000"
      - "100.x.x.x:8812:8812"
    volumes:
      - questdb_data:/var/lib/questdb
    restart: unless-stopped
```

Deploy the stack:
```bash
docker compose up -d
```

---

## Part 6: Connecting from Other Applications

To connect to QuestDB from another application or your local machine:
1. **Install Tailscale** on the client machine.
2. **Log in** using the same Tailscale account.
3. **Use the Tailscale IP**:
   - Connection string: `postgresql://admin:quest@100.x.x.x:8812/qdb`
   - Web UI: `http://100.x.x.x:9000`

By following this guide, your application and database run on powerful, free ARM hardware while remaining completely shielded from public internet threats.
