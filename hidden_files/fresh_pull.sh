#!/bin/bash
# Fresh Docker Hub pulls for the Lampy stack — relaunched 2026-09-19 ~19:30 PDT.
# Previous jobs died when dockerd went down (~17:04 PDT) under proxy failures.
# Uses the current shell proxy env (hatch-egress-proxy); nothing hardcoded.
LOG=~/workspace/forum-stack/hidden_files/docker_pulls_fresh_2026-09-19.log
IMAGES=(
  "timescale/timescaledb-ha:pg16"
  "ollama/ollama:latest"
  "apache/james:3.8.2"
  "python:3.12-slim"
  "httpd:latest"
)
{
echo "[$(date -u '+%F %T UTC')] starting fresh pulls (daemon restarted, registry reachable)"
for img in "${IMAGES[@]}"; do
  for attempt in 1 2 3 4 5 6; do
    echo "[$(date -u '+%F %T UTC')] attempt $attempt/6: docker pull $img"
    if docker pull "$img" 2>&1; then
      echo "[$(date -u '+%F %T UTC')] OK: $img"
      break
    fi
    echo "[$(date -u '+%F %T UTC')] FAILED attempt $attempt: $img — retrying in 60s"
    sleep 60
  done
done
# james fallback: only if 3.8.2 definitively absent
if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q '^apache/james:3.8.2$'; then
  echo "[$(date -u '+%F %T UTC')] james:3.8.2 absent — trying apache/james:latest fallback"
  docker pull "apache/james:latest" 2>&1 | tail -2
fi
echo "[$(date -u '+%F %T UTC')] pull run finished"
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'
} >> "$LOG" 2>&1
