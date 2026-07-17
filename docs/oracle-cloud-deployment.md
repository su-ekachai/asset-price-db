# Oracle Cloud Free Tier Hosting Guide (QuestDB & OHLCV Store)

**Summary**: This guide provides instructions for hosting the asset-price-db and QuestDB on **Oracle Cloud's Always Free Tier** (ARM Ampere A1 shape) using **Tailscale (Mesh VPN)** for 100% free, private, and encrypted connectivity.

---

## 1. Oracle Cloud Infrastructure (OCI) Setup

### 1.1. Provisioning the Compute Instance
Oracle Cloud Always Free Tier offers generous ARM resources (Ampere A1 Flex shape).

- **Name**: `ohlcv-db-node-1`
- **Shape**: `VM.Standard.A1.Flex`
- **OCPUs**: 2 Cores (free limit reduced from 4 in June 2026)
- **Memory**: 12 GB RAM (Total free limit; was 24 GB before June 2026)
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

### 3.2. Prepare the deploy directory

The production stack (`docker-compose.prod.yml`) runs two services: **QuestDB**, and a **scheduler** that loops `ohlcv sync` every `SYNC_INTERVAL` seconds and pings a healthchecks.io dead-man URL on each success. The scheduler runs a **prebuilt ARM64 image pulled from GitHub Container Registry (GHCR)** — it is *not* built on the VM. The image carries the code, so the VM only needs three config files.

```bash
mkdir -p ~/asset-price-db
```
From your Mac (over Tailscale), copy the compose file and your watchlist:
```bash
scp docker-compose.prod.yml symbols.yaml ohlcv-prod-db:~/asset-price-db/
```
`symbols.yaml` is your watchlist — copy `symbols.yaml.example` to `symbols.yaml` and customize it first. It is mounted **read-only** into the scheduler, so you can edit it on the VM and re-run `docker compose up -d` without rebuilding the image.

### 3.3. Environment file (`.env`)

Create `~/asset-price-db/.env` on the VM (never commit it). Variables the prod stack consumes:

| Variable | Required | Example | Purpose |
|---|---|---|---|
| `QUESTDB_PASSWORD` | **yes** | `<strong-random>` | PG-wire password; compose refuses to start on the default `quest`. |
| `HEALTHCHECK_URL` | recommended | `https://hc-ping.com/<uuid>` | Dead-man switch — pinged only after a **successful** sync; silence triggers an alert. |
| `SYNC_INTERVAL` | no (default `300`) | `300` | Seconds between sync runs. |
| `QUESTDB_USER` | no (default `admin`) | `admin` | PG-wire user. |
| `OHLCV_LOG_FORMAT` | no (default `text`) | `json` | Set `json` for structured logs. |
| `OHLCV_LOG_FILE` | no | `/app/logs/ohlcv.log` | In-container log path (ephemeral unless a volume is added). |
| `APP_TAG` | no (default `latest`) | `0.1.0` | Pin a released image version — used to roll back. |

### 3.4. Publish the image (CI) and make it pullable

`.github/workflows/deploy.yml` publishes the image on every `v*` tag:
```bash
git tag v0.1.0 && git push origin v0.1.0
```
This builds a `linux/arm64` image on a native ARM runner and pushes it to `ghcr.io/su-ekachai/asset-price-db` (tagged with the version and `latest`).

**One-time:** make the GHCR package **public** so the VM pulls without a token — GitHub → repo → **Packages** → `asset-price-db` → **Package settings** → **Change visibility** → **Public**. *(Alternatively keep it private and run `docker login ghcr.io` on the VM with a `read:packages` token.)*

### 3.5. First deploy (bootstrap)

On the VM, bring the stack up (pulls QuestDB + the scheduler image), then initialize the schema and run a first sync:
```bash
cd ~/asset-price-db
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py db init
docker compose -f docker-compose.prod.yml exec scheduler uv run python main.py sync -v
```
> QuestDB takes a few seconds to accept connections after `up -d`. If `db init` errors with a connection failure, wait ~10s and re-run it — the stack does not gate on a DB healthcheck (the questdb image ships no HTTP client), so the commands are safe to retry.
Verify both services are healthy and sync succeeds:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f scheduler
```
QuestDB binds to `127.0.0.1` only. To reach the web console from your Mac, tunnel it over Tailscale SSH:
```bash
ssh -L 9000:localhost:9000 ohlcv-prod-db   # then open http://localhost:9000
```

### 3.6. Deploying updates

From your Mac, after pushing a new `v*` tag and letting the Deploy workflow finish:
```bash
make deploy      # ssh ohlcv-prod-db → docker compose pull && up -d
```
**Rollback:** set `APP_TAG=<older-version>` in the VM's `.env`, then `make deploy`.

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
