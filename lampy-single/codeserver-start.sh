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
# With PASSWORD unset: code-server with --auth none, and a loud log line
#                      saying so. The IDE binds 0.0.0.0:8080; on a home
#                      network that is Kit's call.
set -e
if [ -z "${PASSWORD:-}" ]; then
  echo "codeserver-start: WARNING: PASSWORD is not set - starting code-server with --auth none on 0.0.0.0:8080" >&2
  exec /opt/code-server/bin/code-server --bind-addr 0.0.0.0:8080 --auth none /workspace
else
  exec /opt/code-server/bin/code-server --bind-addr 0.0.0.0:8080 --auth password /workspace
fi
