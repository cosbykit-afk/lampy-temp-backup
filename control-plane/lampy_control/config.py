"""Project-wide configuration for the control plane."""
import os

PROJECT_ROOT = os.path.expanduser("~/workspace/forum-stack")
CONTROL_DIR = os.path.join(PROJECT_ROOT, "control-plane")

# Every file operation must resolve inside one of these roots. Nothing
# outside them can be touched, no matter what path is passed in.
ALLOWED_ROOTS = [PROJECT_ROOT]

SCRIPTS_DIR = os.path.join(CONTROL_DIR, "scripts")  # generated .sh audit trail
LOGS_DIR = os.path.join(CONTROL_DIR, "logs")        # execution logs
TRASH_DIR = os.path.join(CONTROL_DIR, "trash")      # remove() moves here; never deletes
