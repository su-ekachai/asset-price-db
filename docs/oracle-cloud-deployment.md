# Oracle Cloud Free Tier Hosting Guide (QuestDB & OHLCV Store)

**Summary**: This guide provides instructions for hosting the asset-price-db and QuestDB on **Oracle Cloud's Always Free Tier** (ARM Ampere A1 shape) using **Tailscale (Mesh VPN)** for 100% free, private, and encrypted connectivity.

---

## 1. Oracle Cloud Infrastructure (OCI) Setup

### 1.1. Provisioning the Compute Instance
Oracle Cloud Always Free Tier offers generous ARM resources (Ampere A1 Flex shape).

- **Name**: `ohlcv-db-node-1`
- **Shape**: `VM.Standard.A1.Flex`
- **OCPUs**: 4 Cores
- **Memory**: 24 GB RAM (Total free limit)
- **Boot Volume**: 50 GB - 200 GB (Balanced Performance)
- **Image**: `Canonical Ubuntu 24.04 Minimal aarch64` (Recommended for database stability, low overhead, and high security)

### 1.2. Virtual Cloud Network (VCN) Configuration
To ensure security, we will minimize public exposure using OCI best practices.

1. Navigate to **Networking > Virtual Cloud Networks**.
2. Select your VCN (e.g., `ohlcv-prod-vcn`) and its **Security List** (e.g., `ohlcv-prod-tailscale-sl`).
3. **Ingress Rules**:
   - **Port 22 (SSH)**: Allow from `0.0.0.0/0` (or restrict to your specific home/office IP for maximum security).
   - **QuestDB Ports (9000, 8812)**: **DO NOT OPEN THESE PORTS** in the OCI Security List. This prevents the public internet from seeing your database.

---

## 2. Server Configuration & Security

### 2.1. Initial Hardening
Connect via SSH:
```bash
ssh -i <your_key> ubuntu@<public_ip>
```
Perform updates and install essential tools:
```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2. Tailscale (Mesh VPN) Setup
Tailscale creates a private, encrypted network between your cloud VM and your other applications.

1. Install Tailscale:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```
2. Authenticate the VM:
   ```bash
   sudo tailscale up
   ```
3. Note the VM's Tailscale IP (e.g., `100.x.x.x`) by running `tailscale ip -4`.

---

## 3. Database & App Deployment

### 3.1. Install Docker & Docker Compose (ARM)
```bash
sudo curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 3.2. Secure Docker Configuration
Modify your `docker-compose.yml` to ensure QuestDB only listens on the **Tailscale interface**. This is a critical security step.

Update the `ports` section for QuestDB:
```yaml
services:
  questdb:
    image: questdb/questdb:latest
    ports:
      # Bind to Tailscale IP ONLY (replace 100.x.x.x with your VM's Tailscale IP)
      - "100.x.x.x:9000:9000" # HTTP (ILP + Web Console)
      - "100.x.x.x:8812:8812" # PG wire protocol
    volumes:
      - questdb_data:/var/lib/questdb
    restart: unless-stopped
```

Deploy the stack:
```bash
docker compose up -d
```

---

## 4. Connecting from Other Applications

To connect other applications securely over the internet:

1. **Install Tailscale** on the client application server or developer machine.
2. **Log in** to the same Tailscale network.
3. **Connection Strings**: Use the Oracle VM's Tailscale IP instead of its public IP.
   - **PostgreSQL (Query)**: `postgresql://admin:quest@100.x.x.x:8812/qdb`
   - **ILP (Ingestion)**: `100.x.x.x:9000`
4. **Automation**: Use a Tailscale **Auth Key** (Service Account) for headless client applications.

---

## 5. Cybersecurity & Maintenance Checklist

- [ ] **SSH Security**: Disable password authentication in `/etc/ssh/sshd_config`. Use SSH keys only.
- [ ] **Firewall**: Use `ufw` or `firewalld` on the VM to block all traffic except `tailscale0` and `ssh`.
- [ ] **Backups**: Use OCI Block Volume Backups (Always Free includes 5 backup slots).
- [ ] **Monitoring**: Enable OCI Monitoring to track CPU/Disk usage.
- [ ] **Authentication**: Ensure the `admin:quest` default password for QuestDB is changed in `config.yaml` and the Docker environment variables if using the Enterprise version or custom authentication plugins.

---

## 6. Pro-Tip: Keeping the Instance Active
Oracle Cloud may reclaim **Always Free** ARM compute instances if they are deemed "idle" for more than 7 days.
To prevent this, ensure your instance meets these minimum usage requirements:
- CPU utilization is above 10% (at least once per 24 hours).
- Memory utilization is above 10%.
- Network throughput is above 0 KBps.

If your ingestion workload is periodic and low-traffic, consider running a small cron job to periodically run a compute-intensive task (like a hash calculation) to keep the instance "active."

---

## 7. Troubleshooting ARM Compatibility
If certain libraries in `main.py` fail to install on ARM, ensure you are using a base image or environment that supports `aarch64` (ARM64). Most modern Python packages (Pandas, Loguru, QuestDB client) support ARM natively.
