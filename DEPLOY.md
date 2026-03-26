# Stromalytix deployment

The demo has two parts: **Streamlit Cloud** (UI, already connected to your GitHub repo) and an optional **CC3D sidecar** on your **Hostinger VPS**.

## Streamlit Cloud

1. Repo: connect `RegCoDev/stromalytix`, main file `app.py`.
2. **Secrets** (dashboard → app → Settings → Secrets):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
OPENAI_API_KEY = "sk-..."
CC3D_API_URL = "http://YOUR_VPS_IP:8001"
CC3D_API_KEY = "same-as-STROMALYTIX_API_KEY-on-VPS"
```

3. First load may take a few minutes while Chroma builds if `data/chroma_db` is not in the repo (see below).

### Chroma / knowledge base on Cloud

If the vector store is not committed, the app runs `ensure_vectorstore()` on first boot (slow). For faster cold starts, build locally and commit `data/chroma_db/` only if your repo policy allows (large binary tree), or run a one-off indexing job in CI.

## Hostinger VPS — CC3D sidecar

**Prerequisites:** Ubuntu 20.04+, 4 GB+ RAM, SSH access (`ssh root@YOUR_VPS_IP`).

### Option A: systemd + `vps_setup.sh`

1. Clone the repo on the VPS (e.g. `/opt/stromalytix`).
2. Run:

```bash
sudo bash /opt/stromalytix/services/cc3d_runner_api/vps_setup.sh
```

3. Edit the service and set a **strong** API key, then enforce it:

```bash
sudo systemctl edit cc3d-runner
```

Add:

```ini
[Service]
Environment="STROMALYTIX_API_KEY=your-long-random-secret"
Environment="STROMALYTIX_ENFORCE_API_KEY=1"
```

4. Open firewall: **TCP 8001** (and 22 for SSH). In Hostinger hPanel, allow inbound 8001 if a cloud firewall is enabled.

5. Start:

```bash
sudo systemctl daemon-reload
sudo systemctl start cc3d-runner
sudo systemctl status cc3d-runner
curl -s http://127.0.0.1:8001/health
```

### Option B: Docker

```bash
cd services/cc3d_runner_api
docker build -t cc3d-runner .
docker run -d --name cc3d-runner --restart unless-stopped \
  -p 8001:8001 \
  -e STROMALYTIX_API_KEY=your-long-random-secret \
  -e STROMALYTIX_ENFORCE_API_KEY=1 \
  cc3d-runner
```

Image listens on **8001** (matches README and `vps_setup.sh`).

### Local dev sidecar

Omit `STROMALYTIX_ENFORCE_API_KEY` or set `STROMALYTIX_ALLOW_WEAK_KEY=1` so default dev keys still work.

### TLS (recommended for production)

Put nginx + Let’s Encrypt in front of the sidecar; expose `https://cc3d.example.com` proxying to `http://127.0.0.1:8001`. Set `CC3D_API_URL` in Streamlit to that HTTPS URL.

## Health check

`GET /health` — no API key required. Returns `status`, `cc3d_available`, `cc3d_python`.

## Troubleshooting

| Issue | Check |
|-------|--------|
| Streamlit “CC3D not configured” | `CC3D_API_URL` / `CC3D_API_KEY` in Streamlit secrets |
| 401 from sidecar | Keys must match exactly (`x-api-key` header) |
| Sidecar exits on start | `STROMALYTIX_ENFORCE_API_KEY=1` with placeholder key — set a real key |
| Connection refused | VPS firewall, wrong port, or service not running |
