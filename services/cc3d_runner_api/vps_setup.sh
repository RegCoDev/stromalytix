#!/bin/bash
# Run once on Hostinger VPS to set up CC3D environment
# Requires: Ubuntu 20.04+, 4GB+ RAM, 10GB+ disk

set -e

echo "=== Installing Miniconda ==="
wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
  -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p /opt/miniconda3
/opt/miniconda3/bin/conda init bash
source ~/.bashrc

echo "=== Installing CompuCell3D ==="
/opt/miniconda3/bin/conda install \
  -c compucell3d \
  -c conda-forge \
  compucell3d python=3.10 -y

echo "=== Installing FastAPI into CC3D env ==="
/opt/miniconda3/envs/cc3d/bin/pip install fastapi uvicorn aiofiles

echo "=== Creating systemd service ==="
cat > /etc/systemd/system/cc3d-runner.service << 'EOF'
[Unit]
Description=Stromalytix CC3D Runner Sidecar
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/stromalytix/services/cc3d_runner_api
Environment="STROMALYTIX_API_KEY=CHANGE_ME_BEFORE_DEPLOY"
Environment="CC3D_PYTHON=/opt/miniconda3/envs/cc3d/bin/python"
ExecStart=/opt/miniconda3/envs/cc3d/bin/uvicorn main:app \
  --host 0.0.0.0 --port 8001 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cc3d-runner
echo "=== Setup complete. Edit STROMALYTIX_API_KEY in service file, then: ==="
echo "systemctl start cc3d-runner"
echo "systemctl status cc3d-runner"
