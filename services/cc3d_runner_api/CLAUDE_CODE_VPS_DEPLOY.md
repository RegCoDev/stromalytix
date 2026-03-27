# Instructions for Claude Code: Stromalytix CC3D sidecar on VPS

Give this entire document to **Claude Code** (or any coding agent). It should run commands **on the VPS via SSH** (or confirm each step with the human).

**Repo:** `RegCoDev/stromalytix` (or your fork).  
**Constraint:** Do **not** merge OpenClaw networking, secrets, or containers with this service unless the human asks later. Use a **different port** and **separate** env / compose stacks for OpenClaw.

---

## Goal

Run the **CC3D runner API** so Streamlit Cloud can call:

- `POST {CC3D_API_URL}/simulate` with JSON body `{"brief": {...}, "max_steps": 1000}` and header **`x-api-key`** equal to the shared secret.
- `GET {CC3D_API_URL}/job/{job_id}` with the same header.

**Code references (in this repo):**

- Sidecar: [`main.py`](./main.py) — FastAPI, port **8001**, `verify_api_key` reads **`x-api-key`**.
- Streamlit client: [`core/cc3d_runner.py`](../../core/cc3d_runner.py) — `CC3D_API_URL`, `CC3D_API_KEY`.

**Health** (no API key): `GET /health` returns `status`, `cc3d_available`, `cc3d_python`.

---

## Preconditions

- **OS:** Ubuntu 20.04+ (or compatible) on the VPS.
- **Resources:** At least **4 GB RAM**, **10 GB+** free disk (conda + CC3D are heavy).
- **Access:** `sudo`, outbound internet (conda + pip).
- **Path:** [`vps_setup.sh`](./vps_setup.sh) assumes the repo at **`/opt/stromalytix`**. Either clone there or after setup edit **`WorkingDirectory=`** in `/etc/systemd/system/cc3d-runner.service` to the directory that contains `main.py` and `runner.py`.

---

## Step 1 — Clone or update the repo

```bash
sudo mkdir -p /opt
sudo chown "$USER":"$USER" /opt   # if needed for non-root clone
git clone https://github.com/RegCoDev/stromalytix.git /opt/stromalytix
# OR: cd /opt/stromalytix && git pull
```

Confirm:

```bash
test -f /opt/stromalytix/services/cc3d_runner_api/main.py && echo OK
```

---

## Step 2 — Choose deployment mode

### Path A: systemd + `vps_setup.sh`

Matches [DEPLOY.md](../../DEPLOY.md).

1. Run the installer (Miniconda → `/opt/miniconda3`, conda env `cc3d` with CompuCell3D, FastAPI/uvicorn in that env, systemd unit **`cc3d-runner`**):

   ```bash
   sudo bash /opt/stromalytix/services/cc3d_runner_api/vps_setup.sh
   ```

2. **Set a strong API key and enforce it.**  
   Placeholder keys (`CHANGE_ME_BEFORE_DEPLOY`, etc.) cause **immediate exit** when `STROMALYTIX_ENFORCE_API_KEY=1` (see startup check in `main.py`).

   Prefer a **systemd override** (does not overwrite the main unit):

   ```bash
   sudo systemctl edit cc3d-runner
   ```

   Add:

   ```ini
   [Service]
   Environment="STROMALYTIX_API_KEY=PASTE_LONG_RANDOM_SECRET_HERE"
   Environment="STROMALYTIX_ENFORCE_API_KEY=1"
   ```

   Then:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart cc3d-runner
   sudo systemctl status cc3d-runner --no-pager
   ```

3. If the repo is **not** under `/opt/stromalytix`, set `WorkingDirectory=` in the unit file to `.../services/cc3d_runner_api` for your actual path, then `daemon-reload` and `restart`.

4. The generated service uses:

   - `CC3D_PYTHON=/opt/miniconda3/envs/cc3d/bin/python`
   - `uvicorn main:app --host 0.0.0.0 --port 8001`

### Path B: Docker

From [`Dockerfile`](./Dockerfile):

```bash
cd /opt/stromalytix/services/cc3d_runner_api
docker build -t cc3d-runner .
docker run -d --name cc3d-runner --restart unless-stopped \
  -p 8001:8001 \
  -e STROMALYTIX_API_KEY=PASTE_LONG_RANDOM_SECRET_HERE \
  -e STROMALYTIX_ENFORCE_API_KEY=1 \
  cc3d-runner
```

Inside the image, `CC3D_PYTHON` defaults to **`/opt/conda/envs/cc3d/bin/python`**. Do not run OpenClaw in this container.

---

## Step 3 — Firewall and hosting panel

- Allow **TCP 8001** inbound on the VPS firewall and **Hostinger hPanel** (or equivalent) cloud firewall if used.
- Keep **SSH (22)** as already configured.
- **Production:** use **nginx + Let’s Encrypt** in front; proxy `https://cc3d.example.com` → `http://127.0.0.1:8001`; set Streamlit `CC3D_API_URL` to that HTTPS URL.

---

## Step 4 — Verification (on VPS)

```bash
curl -s http://127.0.0.1:8001/health
```

Expect `"status": "ok"` and **`cc3d_available": true`** when `CC3D_PYTHON` exists.

Test auth (replace `SECRET` with your key):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://127.0.0.1:8001/simulate \
  -H "Content-Type: application/json" \
  -H "x-api-key: SECRET" \
  -d '{"brief":{},"max_steps":10}'
```

Expect **200** and JSON with `job_id` (empty `brief` may still fail inside CC3D; this checks API + auth).

Optional from another machine:

```bash
curl -s http://VPS_PUBLIC_IP:8001/health
```

---

## Step 5 — Streamlit Cloud secrets

In Streamlit app **Settings → Secrets**:

```toml
CC3D_API_URL = "http://VPS_PUBLIC_IP:8001"
CC3D_API_KEY = "same-secret-as-STROMALYTIX_API_KEY-on-VPS"
```

With HTTPS reverse proxy:

```toml
CC3D_API_URL = "https://cc3d.example.com"
```

The value must match **exactly** (`x-api-key` on requests).

---

## Step 6 — Troubleshooting

| Symptom | Action |
|--------|--------|
| Service exits immediately | `journalctl -u cc3d-runner -n 80 --no-pager` — often placeholder key + `STROMALYTIX_ENFORCE_API_KEY=1` |
| `cc3d_available: false` in `/health` | Fix `CC3D_PYTHON` in unit file or container env |
| Streamlit “Run CC3D” disabled | Set `CC3D_API_URL` / `CC3D_API_KEY` in Cloud secrets |
| 401 from sidecar | `CC3D_API_KEY` ≠ `STROMALYTIX_API_KEY` |
| Connection refused | Firewall, wrong port, service not running |
| Docker build fails | Disk/RAM; consider `docker system prune` (careful) or more swap |

---

## Non-goals (unless human requests)

- Do **not** install OpenClaw inside the `cc3d-runner` image or CC3D conda env.
- Do **not** expose CC3D on extra public ports without reason.
- Do **not** turn off `STROMALYTIX_ENFORCE_API_KEY` on a public IP without another layer (nginx + allowlist, mTLS, etc.).

---

## Deliverables back to the human

1. `systemctl status cc3d-runner` or `docker ps` showing the sidecar running.
2. Output of `curl -s http://127.0.0.1:8001/health`.
3. Confirm: VPS **`STROMALYTIX_API_KEY`** = Streamlit **`CC3D_API_KEY`** (same string).
4. Confirm firewall allows **8001** (or HTTPS-only via nginx).
