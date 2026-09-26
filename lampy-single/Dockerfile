# Lampy single image — the whole stack in one image.
# Kit 2026-09-20: "get this down to one image".
#
# Base: timescale/timescaledb-ha:pg16 (PostgreSQL 16 + TimescaleDB).
# Adds: Apache HTTPD (Debian apache2), Python 3 + pgai, OpenJDK 17 (James),
# Ollama binary (COPY --from the official image), code-server, supervisor.
# All services run under supervisord as PID 1.
#
# IMPORTANT: the base image sets USER postgres and ENTRYPOINT
# /docker-entrypoint.sh — both are reset below (USER root, ENTRYPOINT []),
# otherwise every RUN/COPY runs as postgres and the container would
# boot straight into postgres instead of supervisord.
#
# Build (REQUIRES container execution — build on Windows Docker Desktop,
# not on the Linux reference sandbox where `docker run` is blocked):
#   cd <forum-stack> && ./lampy-single/build.sh
#
# Run (Windows paths shown; PGDATA stays the anchor):
#   docker run -d --name lampy ^
#     -p 80:80 -p 443:443 -p 5432:5432 -p 11434:11434 -p 8080:8080 ^
#     -p 2525:2525 -p 2465:2465 -p 2587:2587 -p 1143:1143 -p 1993:1993 -p 1110:1110 ^
#     -e POSTGRES_PASSWORD=... [-e PASSWORD=...] ^
#   PASSWORD is optional: when unset, code-server stays DISABLED (port 8080
#   stays closed; see codeserver-start.sh). POSTGRES_PASSWORD is required by postgres
#   and the pgai worker.
#     -v C:\Lampy\data\pgdata:/home/postgres/pgdata ^
#     -v C:\Lampy\data\ollama:/root/.ollama ^
#     lampy:latest
#
# Services inside (supervisord):
#   postgres     /docker-entrypoint.sh postgres   (as postgres user; PGDATA init on first boot)
#   apache2      apache2ctl -D FOREGROUND          (port 80; vhost lampy-single/apache2-lampy.conf)
#   ollama       ollama serve                      (0.0.0.0:11434; models in /root/.ollama)
#   james        java -jar james-server-jpa-app.jar (Kit's port remap baked into conf/)
#   code-server  browser IDE on :8080 (PASSWORD env, OPTIONAL since 2026-09-23:
#                codeserver-start.sh DISABLES the IDE when unset, so a
#                missing PASSWORD can never crash supervisord at parse time)
#   pgai-worker  pgai vectorizer worker (POSTGRES_PASSWORD env, required)
#
# Gwen (2026-09-23): the Lampy administrator model (qwen3:0.6b +
# lampy-single/Modelfile.gwen) is baked into /root/.ollama at build time,
# so she is present on first boot with no pull needed. Her system prompt
# ships in the image — anyone who pulls it can read it.
#
# Pending at image build time (unchanged from the multi-service stack):
#   - pgai/pgvectorscale extensions in the DB need the pgrx build (not in image).
#   - xapp (forum app) for the /app reverse proxy is not in the image yet.

# Pinned by digest 2026-09-20 for reproducible builds (see pressure-test.sh
# phase 6). Re-pin deliberately when moving to a newer base.
FROM timescale/timescaledb-ha:pg16@sha256:4f288c0a521362cad799f265bc0ebd60c3f8f98596b850172cc2da72883420ff AS base

FROM base
USER root
ENTRYPOINT []

# Ollama binary donor files, vendored (2026-09-26): extracted byte-identical
# from ollama/ollama:latest@sha256:da6e0dc5651df159e45686fd663c4dbe1624a52c44d7280eeac1551d8f865532
# via the last good image, so the build no longer pulls from Docker Hub
# (the Windows credential helper fails without an interactive logon session).
# Re-vendor deliberately when moving to a newer Ollama.
COPY lampy-single/ollama-donor/usr/bin/ollama /usr/bin/ollama
# The CLI alone cannot run inference: `ollama serve` starts and /api/tags
# works, but every model run fails with "llama-server binary not found"
# because the runner lives in /usr/lib/ollama. Copy the whole lib dir.
COPY lampy-single/ollama-donor/usr/lib/ollama /usr/lib/ollama

# Gwen, baked in: pull the base weights and create the administrator model
# at build time so the image ships with her in /root/.ollama.
# (Build-cloud and Docker Desktop builders have normal internet access;
# the sandbox's egress proxy does not, so do not build this stage there.)
COPY lampy-single/Modelfile.gwen /tmp/Modelfile.gwen
RUN (ollama serve >/tmp/ollama-build.log 2>&1 & echo $! >/tmp/ollama.pid) && \
    sleep 10 && \
    ollama pull qwen3:0.6b && \
    ollama create gwen -f /tmp/Modelfile.gwen && \
    ollama list && \
    kill "$(cat /tmp/ollama.pid)" && \
    rm -f /tmp/Modelfile.gwen /tmp/ollama.pid /tmp/ollama-build.log

RUN mkdir -p /usr/share/man/man1 \
    && apt-get update && apt-get install -y --no-install-recommends \
      apache2 \
      python3 python3-pip \
      openjdk-17-jre-headless \
      supervisor \
    && rm -rf /var/lib/apt/lists/*

# pgAI vectorizer worker dependency — installed from a pre-downloaded
# wheelhouse instead of PyPI. The satellite link repeatedly corrupted or
# killed the giant torch/nvidia wheels mid-build (build attempt 1: SHA256
# mismatch on nvidia-nccl-cu13; attempt 3: buildx EOF during the 554MB
# torch download), so the full dependency closure (208 wheels, ~3.2GB) is
# staged as build-context dir `wheelhouse/` OUT-OF-BAND (not committed to
# git) and pip installs offline with --no-index. torch is pinned to 2.14.0
# to match the staged resolution.
# NOTE: no --break-system-packages here — the base is Ubuntu jammy with
# pip 22.0.2, which predates that flag (pip >= 23) and has no
# EXTERNALLY-MANAGED enforcement, so plain pip install works.
COPY wheelhouse /opt/wheelhouse
RUN pip install --no-cache-dir --no-index --find-links=/opt/wheelhouse \
      "pgai[vectorizer-worker]" torch==2.14.0 \
    && rm -rf /opt/wheelhouse

# James with Kit's config (port remap 2525/2465/2587/1143/1993/1110 in conf/).
COPY james/james-server-jpa-guice /opt/james/james-server-jpa-guice

# code-server: ADD auto-extracts the tarball (no RUN needed for this step).
ADD downloads/code-server-4.138.0-linux-amd64.tar.gz /opt/
RUN ln -s /opt/code-server-4.138.0-linux-amd64 /opt/code-server

# Apache vhost: static htdocs + /app reverse proxy (xapp pending).
COPY lampy-single/apache2-lampy.conf /etc/apache2/sites-available/lampy.conf
COPY httpd/htdocs/ /var/www/html/
RUN a2dissite 000-default && a2ensite lampy && a2enmod proxy proxy_http

# Supervisord program definitions.
COPY lampy-single/supervisord.conf /etc/supervisor/conf.d/lampy.conf
COPY lampy-single/pgai-worker.sh /usr/local/bin/pgai-worker.sh
COPY lampy-single/codeserver-start.sh /usr/local/bin/codeserver-start.sh
RUN chmod +x /usr/local/bin/pgai-worker.sh /usr/local/bin/codeserver-start.sh \
    && mkdir -p /var/log/supervisor /var/run/supervisor \
    && mkdir -p /var/run/apache2 /var/lock/apache2 \
    && rm -rf /tmp/hsperfdata_root

EXPOSE 80 443 5432 11434 8080 2525 2465 2587 1143 1993 1110
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/lampy.conf"]
