#!/bin/bash
# Launch code-server (VS Code in the browser) for the Lampy project.
# Password comes from the CODE_SERVER_PASSWORD env var — never stored in a file.
#   CODE_SERVER_PASSWORD=... bash run-codeserver.sh
# Reference-host smoke test: CODE_SERVER_PASSWORD=dummy bash run-codeserver.sh
set -e
IDE_DIR="$(cd "$(dirname "$0")" && pwd)"
CS="$IDE_DIR/code-server-4.138.0-linux-amd64/bin/code-server"
DATA_DIR="$IDE_DIR/data"
mkdir -p "$DATA_DIR"
exec "$CS" \
  --bind-addr 127.0.0.1:8080 \
  --auth password \
  --user-data-dir "$DATA_DIR/user-data" \
  --extensions-dir "$DATA_DIR/extensions" \
  ~/workspace/forum-stack
