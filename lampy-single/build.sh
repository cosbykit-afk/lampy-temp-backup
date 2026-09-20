#!/bin/sh
# Build the single Lampy image. REQUIRES container execution
# (Windows Docker Desktop) — the Linux reference sandbox blocks
# `docker run`, so RUN steps cannot execute there.
# Run from the forum-stack root (build context).
set -e
cd "$(dirname "$0")/.."
docker build -f lampy-single/Dockerfile -t lampy:latest .
