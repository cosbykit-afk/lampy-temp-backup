#!/bin/bash
# lampy_control — move — 2026-09-19 19:36:08
# runs with administrative privileges; every command below is the audit trail
set -euo pipefail

mkdir -p /home/hatch/workspace/forum-stack/control-plane/demo_area/sub
mv -- /home/hatch/workspace/forum-stack/control-plane/demo_area/hello.txt /home/hatch/workspace/forum-stack/control-plane/demo_area/sub/hello2.txt
