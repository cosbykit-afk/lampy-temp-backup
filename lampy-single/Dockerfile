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
#     -e POSTGRES_PASSWORD=... -e PASSWORD=... ^
#     -v C:\Lampy\data\pgdata:/home/postgres/pgdata ^
#     -v C:\Lampy\data\ollama:/root/.ollama ^
#     lampy:latest
#
# Services inside (supervisord):
#   postgres     /docker-entrypoint.sh postgres   (as postgres user; PGDATA init on first boot)
#   apache2      apache2ctl -D FOREGROUND          (port 80; vhost lampy-single/apache2-lampy.conf)
#   ollama       ollama serve                      (0.0.0.0:11434; models in /root/.ollama)
#   james        java -jar james-server-jpa-app.jar (Kit's port remap baked into conf/)
#   code-server  browser IDE on :8080 (PASSWORD env, required)
#   pgai-worker  pgai vectorizer worker (POSTGRES_PASSWORD env, required)
#
# Pending at image build time (unchanged from the multi-service stack):
#   - pgai/pgvectorscale extensions in the DB need the pgrx build (not in image).
#   - xapp (forum app) for the /app reverse proxy is not in the image yet.

# Pinned by digest 2026-09-20 for reproducible builds (see pressure-test.sh
# phase 6). Re-pin deliberately when moving to a newer base.
FROM timescale/timescaledb-ha:pg16@sha256:4f288c0a521362cad799f265bc0ebd60c3f8f98596b850172cc2da72883420ff AS base

# Ollama binary donor stage (verified path /usr/bin/ollama in image layers).
FROM ollama/ollama:latest@sha256:da6e0dc5651df159e45686fd663c4dbe1624a52c44d7280eeac1551d8f865532 AS ollama-src

FROM base
USER root
ENTRYPOINT []

COPY --from=ollama-src /usr/bin/ollama /usr/bin/ollama
# The CLI alone cannot serve: it execs the llama-server runner from
# /usr/lib/ollama. Without this, `ollama serve` fails at startup.
COPY --from=ollama-src /usr/lib/ollama /usr/lib/ollama

RUN mkdir -p /usr/share/man/man1 \
    && apt-get update && apt-get install -y --no-install-recommends \
      apache2 \
      python3 python3-pip \
      openjdk-17-jre-headless \
      supervisor \
    && rm -rf /var/lib/apt/lists/*

# pgAI vectorizer worker dependency (the DB-side pgai extension still
# needs the pgrx build; the worker starts regardless and polls).
# NOTE: no --break-system-packages here — the base is Ubuntu jammy with
# pip 22.0.2, which predates that flag (pip >= 23) and has no
# EXTERNALLY-MANAGED enforcement, so plain pip install works.
RUN pip install --no-cache-dir pgai

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
RUN chmod +x /usr/local/bin/pgai-worker.sh \
    && mkdir -p /var/log/supervisor /var/run/supervisor \
    && mkdir -p /var/run/apache2 /var/lock/apache2 \
    && rm -rf /tmp/hsperfdata_root

EXPOSE 80 443 5432 11434 8080 2525 2465 2587 1143 1993 1110
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/lampy.conf"]
