#!/bin/sh
# code-server entrypoint for the Lampy single image.
#
# Tolerates an unset or empty PASSWORD. supervisord cannot expand
# %(ENV_PASSWORD)s when the variable is absent from the container
# environment, and that parse failure used to take down the ENTIRE
# container (all services) at boot. This wrapper reads PASSWORD from the
# inherited environment instead, so supervisord.conf contains no
# %(ENV_...)s expansions at all.
#
# With PASSWORD set:   code-server with password auth (PASSWORD env).
# With PASSWORD unset: code-server stays DISABLED. The wrapper logs the
#                      fact and then idles (keeping the supervisord program
#                      in RUNNING state) WITHOUT opening port 8080. The IDE
#                      is never exposed unauthenticated merely because the
#                      password is absent. Set PASSWORD and restart the
#                      container to enable the IDE.
set -e
if [ -z "${PASSWORD:-}" ]; then
  echo "codeserver-start: PASSWORD is not set - code-server DISABLED. Port 8080 stays closed. Set PASSWORD and restart to enable the IDE." >&2
  # Idle forever so supervisord keeps this program RUNNING and the rest of
  # the container (postgres, httpd, ollama, james, worker) is unaffected.
  exec tail -f /dev/null
else
  exec /opt/code-server/bin/code-server --bind-addr 0.0.0.0:8080 --auth password /workspace
fi
