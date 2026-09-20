#!/bin/sh
# pgai vectorizer worker entrypoint for the Lampy single image.
# Assembles the DB URL from POSTGRES_PASSWORD at container run time
# (supervisord cannot interpolate one env var into another).
set -e
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD at run time}"
exec /usr/bin/python3 -m pgai vectorizer worker \
  --poll-interval 30s \
  --db-url "postgres://postgres:${POSTGRES_PASSWORD}@localhost:5432/postgres"
