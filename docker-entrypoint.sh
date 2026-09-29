#!/bin/sh
# Runs inside the cloudlens container. config.yaml and cloudlens.db both live
# in /app/data, which docker-compose mounts as a single directory volume --
# bind-mounting a lone file that doesn't yet exist on the host is a classic
# Docker gotcha (Docker silently creates a directory there instead).
set -e

mkdir -p /app/data
cd /app/data

if [ ! -f config.yaml ]; then
    cp /app/config.example.yaml config.yaml
    echo "Created data/config.yaml from config.example.yaml (demo mode)."
fi

echo "Running initial sync..."
cloudlens sync
echo "Running initial analysis..."
cloudlens analyze

exec streamlit run /app/dashboard/app.py --server.address=0.0.0.0 --server.port=8501
