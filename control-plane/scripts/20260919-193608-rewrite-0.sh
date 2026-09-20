#!/bin/bash
# lampy_control — rewrite — 2026-09-19 19:36:08
# runs with administrative privileges; every command below is the audit trail
set -euo pipefail

mkdir -p /home/hatch/workspace/forum-stack/control-plane/demo_area
base64 -d > /home/hatch/workspace/forum-stack/control-plane/demo_area/hello.txt << 'LAMPY_EOF'
aGVsbG8gbGFtcHkKc2Vjb25kIGxpbmUK
LAMPY_EOF
