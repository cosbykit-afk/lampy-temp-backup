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
set -e
cd "$(dirname "$0")/.."
docker buildx build \
  --builder lampy-cloud \
  --platform linux/amd64 \
  -f lampy-single/Dockerfile \
  -t kitcosby/lampy-single:latest \
  --push \
  .
