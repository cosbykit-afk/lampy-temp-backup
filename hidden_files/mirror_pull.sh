#!/bin/bash
# Pull Lampy base images via Google's Docker Hub mirror (mirror.gcr.io),
# retag to canonical Hub names. Anonymous pulls only.
log="$HOME/workspace/forum-stack/hidden_files/docker_pulls_mirror_2026-09-19.log"
{
echo "=== Google mirror pull run started $(date -u +%FT%TZ) ==="
df -h / /var/lib/docker 2>/dev/null | head -5
have() { docker images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | grep -qx "$1"; }
mirror_for() {
  case "$1" in
    nginx:*|python:*) echo "mirror.gcr.io/library/$1" ;;
    *) echo "mirror.gcr.io/$1" ;;
  esac
}
for img in timescale/timescaledb-ha:pg16 ollama/ollama:latest nginx:latest python:3.12-slim; do
  if have "$img"; then echo "HAVE $img -- skipping"; continue; fi
  m="$(mirror_for "$img")"
  ok=0
  for attempt in 1 2 3 4; do
    echo "--- pull $m (attempt $attempt/4) ---"
    if timeout 300 docker pull "$m" > /tmp/pull_out.txt 2>&1; then
      tail -3 /tmp/pull_out.txt
      if have "$m"; then
        if docker tag "$m" "$img"; then echo "TAGGED $m as $img"; else echo "TAG FAILED for $m"; fi
        ok=1; break
      else
        echo "pull exited 0 but $m not listed by docker images"
      fi
    else
      echo "exit=$? : $(tail -2 /tmp/pull_out.txt | tr '\n' ' ')"
    fi
    if [ "$attempt" -lt 4 ]; then sleep 30; fi
  done
  if [ $ok -eq 1 ]; then echo "DONE $img"; else echo "INCOMPLETE $img"; fi
done
echo "=== finished $(date -u +%FT%TZ) ==="
docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}"
} >> "$log" 2>&1
