#!/bin/sh
# Build the single Lampy image on the Docker Build Cloud builder
# "lampy" (endpoint kitcosby/lampy) and push it to Docker Hub so the
# Windows machine can pull it later.
#
# PREREQUISITES (one time):
#   1. docker login          # Docker Hub login on THIS machine
#   2. docker buildx create --name lampy-cloud --driver cloud kitcosby/lampy
#
# The cloud driver cannot --load into a local daemon, so the image is
# pushed to the registry with --push.
#
# Run from anywhere; the build context is forum-stack/.
#
# SANDBOX NOTE (2026-09-20): on the Linux reference sandbox, the egress
# proxy breaks the cloud driver's TLS to build-cloud.docker.com, and the
# driver needs Docker Hub credentials for the cloud API. If the build fails
# with "tls: first record does not look like a TLS handshake", run it
# through the relay:
#   1. Start the relay (background):  python3 /tmp/cloud_relay.py
#      (recreate it if missing — it forwards 127.0.0.1:443 to
#      build-cloud.docker.com:443 via the proxy's HTTP CONNECT).
#   2. Verify: curl --resolve build-cloud.docker.com:443:127.0.0.1 \
#        https://build-cloud.docker.com/v2/   # expect 401
#   3. Run the build in a mount namespace with a hosts override so the
#      driver resolves build-cloud.docker.com to the relay:
#        unshare -m bash -c '
#          cp /etc/hosts /tmp/hosts.build
#          echo "127.0.0.1 build-cloud.docker.com" >> /tmp/hosts.build
#          mount --bind /tmp/hosts.build /etc/hosts
#          exec ./lampy-single/build-cloud.sh'
#   4. Kill the relay and remove /tmp/cloud_relay.py /tmp/hosts.build after.
# If it fails with "no credentials found for https://index.docker.io/v1/",
# run `docker login` first (needs the Docker Hub PAT — the Secure Vault
# cannot release it to the CLI, so this step needs Kit).
set -e
cd "$(dirname "$0")/.."
docker buildx build \
  --builder lampy-cloud \
  --platform linux/amd64 \
  -f lampy-single/Dockerfile \
  -t kitcosby/lampy-single:latest \
  --push \
  .
