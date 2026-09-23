#!/usr/bin/env bash
# pressure-test.sh — pressure-test workflow for the lampy-single image.
#
# Goal: make the best image we can provide, by testing the configuration
# as hard as possible and fixing every finding before shipping.
#
# What it does (all without running a container — the sandbox blocks
# `docker run`, so runtime checks are labeled SKIP here and run later
# on Windows Docker Desktop):
#   1. build-provenance  — image exists in registry, digest matches local
#   2. static-audit      — every expected file/binary/config is in the image,
#                          with the right executable bits and symlinks
#   3. config-syntax     — supervisord.conf parses; apache vhost is sane;
#                          pgai-worker.sh passes `sh -n`
#   4. smoke-chroot      — binaries actually execute (unshare+chroot):
#                          ollama/java/python3-pgai/code-server/apache2/
#                          supervisord/postgres --version or configtest
#   5. secret-scan       — no PATs, private keys, or tokens baked into layers
#   6. size-hygiene      — image size, layer breakdown, leftover caches
#
# Usage: ./pressure-test.sh [image]
# Exit: 0 if no FAIL, 1 otherwise. SKIP is not failure but is reported.
#   Exit 2 = the harness itself is broken (missing tool on PATH).
# Notation contract (WORKFLOW.md §6.1): every check emits exactly one
#   RESULT<TAB><PASS|FAIL|SKIP><TAB><name><TAB><reason> record line;
#   the run ends with one SUMMARY<TAB>pass=N<TAB>fail=M<TAB>skip=K line.
#   Check names are single-line, tab-free. `set -o pipefail` is on, so a
#   failure anywhere in a pipeline fails the check (pipes must not mask
#   exit codes).
#
# Re-run after every Dockerfile/config change + rebuild. Findings go to
# BUGLOG.md; fixes go in the Dockerfile; the loop ends when this is clean.

set -u
# pipefail: a pipeline's exit status is the LAST NONZERO status in the pipe,
# not the last command's. Without this, `docker export | tar` reports tar's
# success even when docker export fails, and `imagetools inspect | grep`
# hides an inspect failure. (Workspace lesson: pipes mask exit codes —
# never trust `cmd | tail`-style pipelines for pass/fail.)
set -o pipefail
IMAGE="${1:-kitcosby/lampy-single:latest}"
# NOTE: /tmp on this machine is a 512MB tmpfs — far too small for a ~3GB
# image export. Work goes under ~/workspace instead.
WORK_BASE="${PRESSURE_WORK_BASE:-$HOME/workspace/.pressure-work}"
mkdir -p "$WORK_BASE"
WORK="$(mktemp -d "$WORK_BASE/lampy-pressure.XXXXXX")"
ROOTFS="$WORK/rootfs"
PASS=0; FAIL=0; SKIP=0
FAILED_CHECKS=()

log()  { printf '%s\n' "$*"; }
# result(): machine-readable record for every check, one per line:
#   RESULT<TAB><PASS|FAIL|SKIP><TAB><check name><TAB><reason or empty>
# Check names are single-line and contain no tabs, so `grep '^RESULT'`
# output is reliably parseable and diffable across runs. The human-readable
# PASS/FAIL/SKIP lines above are the log; these records are the notation.
result() { printf 'RESULT\t%s\t%s\t%s\n' "$1" "$2" "$3"; }
pass() { PASS=$((PASS+1)); log "PASS  $1"; result PASS "$1" ""; }
fail() { FAIL=$((FAIL+1)); FAILED_CHECKS+=("$1"); log "FAIL  $1${2:+  -- $2}"; result FAIL "$1" "${2:-}"; }
skip() { SKIP=$((SKIP+1)); log "SKIP  $1${2:+  -- $2}"; result SKIP "$1" "${2:-}"; }

need() { command -v "$1" >/dev/null 2>&1 || { log "FATAL: need '$1' on PATH"; exit 2; }; }
need docker; need python3

log "=== lampy-single pressure test ==="
log "image: $IMAGE"
log "workdir: $WORK"
log ""

# ---------------------------------------------------------------- phase 0
log "--- phase 0: local image + export ---"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    log "pulling $IMAGE ..."
    docker pull "$IMAGE" >/dev/null 2>&1 \
        && pass "image pulls clean" \
        || { fail "image pulls clean" "docker pull failed"; }
else
    pass "image present locally"
fi

REG_DIGEST="$(docker buildx imagetools inspect "$IMAGE" 2>/dev/null \
    | grep -m1 '^Digest:' | awk '{print $2}')"
LOCAL_DIGEST="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null)"
log "registry digest: ${REG_DIGEST:-unknown}"
log "local image id:  ${LOCAL_DIGEST:-unknown}"
[ -n "${REG_DIGEST:-}" ] && pass "registry digest readable" \
    || fail "registry digest readable"

CID="$(docker create "$IMAGE" 2>/dev/null)" \
    && pass "docker create works (no run needed)" \
    || fail "docker create works"
log "exporting container filesystem (this takes a while) ..."
mkdir -p "$ROOTFS"
# NOTE: this sandbox denies custom uid_map writes, so tar cannot preserve the
# image's real ownership (everything ends up owned by us). That is fine for
# every check below — permission BITS are preserved, and the smoke tests run
# as root inside a userns anyway. --no-same-owner silences the chown noise.
docker export "$CID" | tar --no-same-owner -x -C "$ROOTFS" \
    && pass "filesystem exported" \
    || fail "filesystem exported"
docker rm "$CID" >/dev/null 2>&1
log ""

# ---------------------------------------------------------------- phase 1
log "--- phase 1: static file audit ---"
# Resolve an image-absolute path against the exported rootfs, following
# symlinks *inside* the rootfs. Plain `[ -e $ROOTFS$path ]` lets absolute
# symlinks (e.g. /var/run -> /run, /opt/code-server -> /opt/code-server-*)
# escape to the HOST filesystem and produces false FAILs.
resolve() {
python3 - "$ROOTFS" "$1" <<'EOF'
import os, sys
root, p = sys.argv[1], sys.argv[2]
parts = [x for x in p.strip('/').split('/') if x]
cur_parts = []
hops = 0
i = 0
while i < len(parts):
    cur_parts.append(parts[i])
    full = root + '/' + '/'.join(cur_parts)
    if os.path.islink(full):
        target = os.readlink(full)
        if target.startswith('/'):
            parts = [x for x in target.strip('/').split('/') if x] + parts[i+1:]
        else:
            base = cur_parts[:-1]
            parts = base + [x for x in target.split('/') if x not in ('', '.')] + parts[i+1:]
            # collapse any '..' against base
            norm = []
            for x in parts:
                if x == '..':
                    if norm: norm.pop()
                else: norm.append(x)
            parts = norm
        cur_parts = []
        i = 0
        hops += 1
        if hops > 40:
            print('RESOLVE_LOOP'); sys.exit(0)
        continue
    i += 1
print(root + '/' + '/'.join(cur_parts))
EOF
}

# $1=path in image, $2=kind: f=file d=dir x=executable l=symlink
chk() {
    local p="$1" kind="$2" r
    r="$(resolve "$p")"
    case "$kind" in
        f) [ -f "$r" ] && pass "$p present" || fail "$p present" ;;
        d) [ -d "$r" ] && pass "$p present" || fail "$p present" ;;
        x) [ -x "$r" ] && [ -f "$r" ] && pass "$p executable" || fail "$p executable" "missing or not executable" ;;
        l) [ -L "$ROOTFS$p" ] && pass "$p symlink -> $(readlink "$ROOTFS$p")" || fail "$p symlink" ;;
    esac
}

chk /usr/bin/ollama x
# The CLI execs its inference runner from /usr/lib/ollama; without it
# `ollama serve` starts but every model run fails with
# "llama-server binary not found" (real bug found 2026-09-20 via chroot
# inference test).
chk /usr/lib/ollama/llama-server x
chk /usr/lib/jvm/java-17-openjdk-amd64/bin/java x
chk /opt/james/james-server-jpa-guice d
chk /opt/code-server l
chk /opt/code-server/bin/code-server x
chk /etc/apache2/sites-available/lampy.conf f
chk /etc/apache2/sites-enabled/lampy.conf l
chk /etc/apache2/mods-enabled/proxy.load f
chk /etc/apache2/mods-enabled/proxy_http.load f
chk /var/www/html d
chk /etc/supervisor/conf.d/lampy.conf f
chk /usr/local/bin/pgai-worker.sh x
chk /var/log/supervisor d
chk /var/run/supervisor d
chk /docker-entrypoint.sh x
chk /usr/bin/supervisord x
chk /usr/lib/postgresql/16/bin/postgres x

# James jar: supervisord runs `java -jar james-server-jpa-app.jar` with
# directory=/opt/james/james-server-jpa-guice — the jar must exist there.
if [ -f "$ROOTFS/opt/james/james-server-jpa-guice/james-server-jpa-app.jar" ]; then
    pass "james jar at expected path"
else
    fail "james jar at expected path" \
        "supervisord would fail to start james; contents: $(ls "$ROOTFS/opt/james/james-server-jpa-guice" 2>/dev/null | head -5 | tr '\n' ' ')"
fi

# code-server symlink must resolve to a real extracted directory.
r="$(resolve /opt/code-server)"
if [ -d "$r" ]; then
    pass "code-server symlink resolves"
else
    fail "code-server symlink resolves" "points at $(readlink "$ROOTFS/opt/code-server")"
fi

# pgai python package must be importable (check site-packages directly).
if ls "$ROOTFS"/usr/local/lib/python3.10/dist-packages/pgai >/dev/null 2>&1; then
    pass "pgai package installed"
else
    fail "pgai package installed"
fi

# apt lists must be gone (Dockerfile rm -rf /var/lib/apt/lists/*).
if [ -z "$(ls -A "$ROOTFS/var/lib/apt/lists" 2>/dev/null | grep -v '^lock' )" ]; then
    pass "apt lists cleaned"
else
    fail "apt lists cleaned" "leftover files bloat the image"
fi

# Image metadata: USER root, ENTRYPOINT cleared, CMD = supervisord.
USER_V="$(docker image inspect "$IMAGE" --format '{{.Config.User}}' 2>/dev/null)"
[ "$USER_V" = "root" ] && pass "image USER is root" || fail "image USER is root" "got '$USER_V'"
ENTRY="$(docker image inspect "$IMAGE" --format '{{json .Config.Entrypoint}}' 2>/dev/null)"
case "$ENTRY" in "[]"|"null") pass "ENTRYPOINT cleared" ;; *) fail "ENTRYPOINT cleared" "got $ENTRY" ;; esac
CMD_V="$(docker image inspect "$IMAGE" --format '{{json .Config.Cmd}}' 2>/dev/null)"
case "$CMD_V" in *supervisord*) pass "CMD runs supervisord" ;; *) fail "CMD runs supervisord" "got $CMD_V" ;; esac
log ""

# ---------------------------------------------------------------- phase 2
log "--- phase 2: config syntax ---"
SUP="$ROOTFS/etc/supervisor/conf.d/lampy.conf"
python3 - "$SUP" <<'EOF' && pass "supervisord.conf parses" || fail "supervisord.conf parses"
import configparser, sys
c = configparser.ConfigParser()
c.read(sys.argv[1])
progs = [s for s in c.sections() if s.startswith('program:')]
assert progs, "no [program:*] sections"
print("programs:", ", ".join(s.split(':',1)[1] for s in progs))
EOF

# Regression (2026-09-22 boot crash): no %(ENV_...)s expansion may remain in
# supervisord.conf — an unset variable makes supervisord refuse the WHOLE
# config and the container exits before any service starts. Programs that
# need env must read it from the inherited environment (see
# codeserver-start.sh), never via %(ENV_...)s.
if grep -q '%(ENV_' "$SUP"; then
    fail "supervisord.conf has no ENV expansion" \
        "$(grep -o '%(ENV_[A-Za-z_]*)s' "$SUP" | sort -u | tr '\n' ' ')"
else
    pass "supervisord.conf has no ENV expansion"
fi
# The codeserver wrapper must exist, be executable, and tolerate empty PASSWORD.
CS="$ROOTFS/usr/local/bin/codeserver-start.sh"
if [ -x "$CS" ] && grep -q 'PASSWORD:-' "$CS"; then
    pass "codeserver-start.sh tolerates missing PASSWORD"
else
    fail "codeserver-start.sh tolerates missing PASSWORD" "missing, not executable, or no \${PASSWORD:-} guard"
fi
# Missing PASSWORD must DISABLE code-server, never expose it unauthenticated.
if grep -q -- '--auth none' "$CS"; then
    fail "codeserver-start.sh never uses --auth none" "found --auth none: unauthenticated exposure"
else
    pass "codeserver-start.sh never uses --auth none"
fi

# every supervisord command= binary and directory= must exist in the image
# (resolved inside the rootfs — absolute symlinks must not escape to host).
python3 - "$SUP" "$ROOTFS" <<'EOF' && pass "supervisord commands/dirs exist" || fail "supervisord commands/dirs exist"
import configparser, sys, os
sup, root = sys.argv[1], sys.argv[2]
def resolve(p):
    parts = [x for x in p.strip('/').split('/') if x]
    cur, hops, i = [], 0, 0
    while i < len(parts):
        cur.append(parts[i])
        full = root + '/' + '/'.join(cur)
        if os.path.islink(full):
            t = os.readlink(full)
            rest = parts[i+1:]
            if t.startswith('/'):
                parts = [x for x in t.strip('/').split('/') if x] + rest
            else:
                parts = cur[:-1] + [x for x in t.split('/') if x not in ('', '.')] + rest
                norm = []
                for x in parts:
                    if x == '..':
                        if norm: norm.pop()
                    else: norm.append(x)
                parts = norm
            cur, i, hops = [], 0, hops + 1
            assert hops <= 40, "symlink loop"
            continue
        i += 1
    return root + '/' + '/'.join(cur)
c = configparser.ConfigParser(); c.read(sup)
ok = True
for s in c.sections():
    if not s.startswith('program:'): continue
    name = s.split(':',1)[1]
    cmd = c[s]['command'].split()[0]
    if not os.path.exists(resolve(cmd)):
        print(f"  MISSING binary for [{name}]: {cmd}"); ok = False
    if 'directory' in c[s] and not os.path.isdir(resolve(c[s]['directory'])):
        print(f"  MISSING directory for [{name}]: {c[s]['directory']}"); ok = False
sys.exit(0 if ok else 1)
EOF

# every supervisord log dir's parent must exist (same rootfs resolution).
python3 - "$SUP" "$ROOTFS" <<'EOF' && pass "supervisord log dirs exist" || fail "supervisord log dirs exist"
import configparser, sys, os
sup, root = sys.argv[1], sys.argv[2]
def resolve(p):
    parts = [x for x in p.strip('/').split('/') if x]
    cur, hops, i = [], 0, 0
    while i < len(parts):
        cur.append(parts[i])
        full = root + '/' + '/'.join(cur)
        if os.path.islink(full):
            t = os.readlink(full)
            rest = parts[i+1:]
            if t.startswith('/'):
                parts = [x for x in t.strip('/').split('/') if x] + rest
            else:
                parts = cur[:-1] + [x for x in t.split('/') if x not in ('', '.')] + rest
                norm = []
                for x in parts:
                    if x == '..':
                        if norm: norm.pop()
                    else: norm.append(x)
                parts = norm
            cur, i, hops = [], 0, hops + 1
            assert hops <= 40, "symlink loop"
            continue
        i += 1
    return root + '/' + '/'.join(cur)
c = configparser.ConfigParser(); c.read(sup)
ok = True
for s in c.sections():
    for k in ('stdout_logfile','stderr_logfile','logfile','childlogdir','pidfile'):
        if k in c[s]:
            d = os.path.dirname(resolve(c[s][k]))
            if not os.path.isdir(d):
                print(f"  MISSING log dir for [{s}] {k}: {d}"); ok = False
sys.exit(0 if ok else 1)
EOF

# apache vhost: balanced tags + required directives.
VHOST="$ROOTFS/etc/apache2/sites-available/lampy.conf"
python3 - "$VHOST" <<'EOF' && pass "apache vhost sane" || fail "apache vhost sane"
import re, sys
t = open(sys.argv[1]).read()
opens = re.findall(r'<(\w+)[ >]', t); closes = re.findall(r'</(\w+)>', t)
assert sorted(opens) == sorted(closes), f"unbalanced tags: {opens} vs {closes}"
assert 'DocumentRoot' in t, "no DocumentRoot"
print("vhost ok, tags:", opens)
EOF

# pgai-worker.sh must pass sh -n.
sh -n "$ROOTFS/usr/local/bin/pgai-worker.sh" \
    && pass "pgai-worker.sh syntax ok" \
    || fail "pgai-worker.sh syntax ok"
log ""

# ---------------------------------------------------------------- phase 3
log "--- phase 3: binary smoke tests (chroot, no container) ---"
# unshare -rm gives a userns where we are root; chroot into the image fs.
# Binaries run for real (same arch), but this is NOT a runtime test:
# no PID 1, no service supervision, no postgres-as-postgres.
if unshare -rm true 2>/dev/null; then
    pass "user+mount namespace available for chroot"
    smoke() { # $1=label, $2...=command inside chroot
        local label="$1"; shift
        if unshare -rm chroot "$ROOTFS" "$@" >/dev/null 2>&1; then
            pass "smoke: $label"
        else
            fail "smoke: $label" "exit != 0"
        fi
    }
    smoke "ollama --version"        /usr/bin/ollama --version
    # Java: this sandbox's loader does not honor $ORIGIN/RPATH inside a
    # chroot+userns (proven 2026-09-20 with a control binary: $ORIGIN works
    # on the host, fails in chroot+userns). Real containers resolve $ORIGIN
    # normally, so the smoke test sets LD_LIBRARY_PATH to the same dir the
    # RPATH points at. What matters: the binary and its libs are intact.
    smoke "java -version"           /bin/bash -c 'LD_LIBRARY_PATH=/usr/lib/jvm/java-17-openjdk-amd64/lib exec /usr/lib/jvm/java-17-openjdk-amd64/bin/java -version'
    smoke "python3 imports pgai"    /usr/bin/python3 -c "import pgai"
    smoke "code-server --version"   /opt/code-server/bin/code-server --version
    smoke "supervisord --version"   /usr/bin/supervisord --version
    smoke "postgres --version"      /usr/lib/postgresql/16/bin/postgres --version
    # apache2ctl is unusable in this sandbox (ulimit/chown need real root),
    # but it only wraps envvars + apache2. Source envvars directly instead.
    smoke "apache2 configtest"      /bin/bash -c 'source /etc/apache2/envvars && exec /usr/sbin/apache2 -t -f /etc/apache2/apache2.conf'
    smoke "pgai-worker.sh --help"   /usr/bin/python3 -m pgai vectorizer worker --help
else
    skip "chroot smoke tests" "unshare -rm not permitted in this sandbox"
fi
log ""

# ---------------------------------------------------------------- phase 4
log "--- phase 4: secret scan (patterns only, values never printed) ---"
# Tier 1: Docker PATs — zero tolerance; this is our actual credential type.
T1="$(grep -rIlE 'dckr_pat_[A-Za-z0-9_-]+' "$ROOTFS" 2>/dev/null)"
if [ -z "$T1" ]; then
    pass "no Docker PATs in image"
else
    fail "no Docker PATs in image" \
        "matches: $(echo "$T1" | sed "s|$ROOTFS||" | tr '\n' ' ')"
fi
# Tier 2: other key/token-looking material. Known-benign set, triaged
# 2026-09-20: Debian's snakeoil placeholder cert, key-parsing *source code*
# and test fixtures inside node_modules, awscli's own source referencing
# config key names. Anything outside that set fails.
T2="$(grep -rIlE 'BEGIN (RSA )?PRIVATE KEY|BEGIN OPENSSH PRIVATE KEY|aws_secret_access_key|ghp_[A-Za-z0-9]{20,}' "$ROOTFS" 2>/dev/null \
    | grep -vE '/etc/ssl/private/ssl-cert-snakeoil\.key$|/node_modules/|/dist-packages/')"
if [ -z "$T2" ]; then
    pass "no unexpected key/token material in image"
else
    fail "no unexpected key/token material in image" \
        "matches: $(echo "$T2" | sed "s|$ROOTFS||" | tr '\n' ' ' | cut -c1-300)"
fi
# Also scan the repo build context (Dockerfile, confs, scripts).
CTX="$(cd "$(dirname "$0")" && pwd)"
CHITS="$(grep -rIlE 'ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|dckr_pat_[A-Za-z0-9_\-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|xox[bap]-' \
    "$CTX/Dockerfile" "$CTX/supervisord.conf" \
    "$CTX/pgai-worker.sh" "$CTX/apache2-lampy.conf" "$CTX/build-cloud.sh" 2>/dev/null)"
if [ -z "$CHITS" ]; then
    pass "no secret patterns in build context files"
else
    fail "no secret patterns in build context files" "matches in: $CHITS"
fi
log ""

# ---------------------------------------------------------------- phase 5
log "--- phase 5: size & hygiene ---"
SIZE="$(docker image inspect "$IMAGE" --format '{{.Size}}' 2>/dev/null)"
log "image size: $((SIZE/1024/1024)) MB"
log "largest layers (docker history):"
docker history "$IMAGE" --no-trunc --format '{{.Size}}\t{{.CreatedBy}}' 2>/dev/null \
    | sort -rh | head -8 | cut -c1-120
# pip cache must be absent (--no-cache-dir).
if [ -d "$ROOTFS/root/.cache/pip" ] && [ -n "$(ls -A "$ROOTFS/root/.cache/pip" 2>/dev/null)" ]; then
    fail "pip cache absent"
else
    pass "pip cache absent"
fi
# code-server tarball must not be retained (ADD extracts, tarball not kept).
if ls "$ROOTFS"/opt/*.tar.gz >/dev/null 2>&1; then
    fail "no leftover tarballs in /opt" "$(ls "$ROOTFS"/opt/*.tar.gz | head -3)"
else
    pass "no leftover tarballs in /opt"
fi
# /tmp should hold nothing we added. Known-benign: extversions.amd64.zCoF
# ships inside the timescale base image; hsperfdata_root (JVM build-time
# droppings) is cleaned by the Dockerfile since 2026-09-20.
TMP_LEFT="$(ls -A "$ROOTFS/tmp" 2>/dev/null | grep -v '^extversions\.amd64\.')"
if [ -z "$TMP_LEFT" ]; then
    pass "/tmp clean (besides base-image leftover)"
else
    fail "/tmp clean" "unexpected: $(echo "$TMP_LEFT" | tr '\n' ' ')"
fi
log ""

# ---------------------------------------------------------------- phase 6
log "--- phase 6: Dockerfile lint (static rules) ---"
DF="$CTX/Dockerfile"
grep -qE 'dckr_pat_|password\s*=\s*[^$"]{8,}' "$DF" \
    && fail "no literal secrets in Dockerfile" \
    || pass "no literal secrets in Dockerfile"
# base images should be pinned by digest for reproducibility.
if grep -qE '^FROM [^ ]+@sha256:' "$DF"; then
    pass "base images pinned by digest"
else
    fail "base images pinned by digest" \
        "tags float; pin: timescale/timescaledb-ha:pg16 and ollama/ollama digests from the build log"
fi
# EXPOSE ports should cover the supervisord services' ports.
for p in 80 5432 11434 8080; do
    grep -q "EXPOSE.*\b$p\b" "$DF" && pass "port $p exposed" || fail "port $p exposed"
done
# james ports from the v1 remap must all be exposed.
for p in 2525 2465 2587 1143 1993 1110; do
    grep -q "EXPOSE.*\b$p\b" "$DF" && pass "james port $p exposed" || fail "james port $p exposed"
done
log ""

# ---------------------------------------------------------------- deferred
log "--- deferred: runtime checks (need a real container; run on Windows) ---"
skip "postgres init + TimescaleDB extension loads" "needs docker run"
skip "apache serves / on :80; /app proxy behavior" "needs docker run"
skip "ollama serve responds on :11434" "needs docker run"
skip "james SMTP banner on :2525 + send/receive" "needs docker run"
skip "code-server login on :8080" "needs docker run"
skip "pgai worker polls without crash" "needs docker run"
skip "TLS on :443 (no vhost configured yet)" "needs certs + docker run"
log ""

# ---------------------------------------------------------------- summary
log "=== summary ==="
log "PASS: $PASS   FAIL: $FAIL   SKIP: $SKIP"
printf 'SUMMARY\tpass=%d\tfail=%d\tskip=%d\n' "$PASS" "$FAIL" "$SKIP"
if [ "$FAIL" -gt 0 ]; then
    log "failed checks:"
    printf '  - %s\n' "${FAILED_CHECKS[@]}"
    log "Fix, rebuild, re-run. Findings -> BUGLOG.md."
    log "(workdir kept for debugging: $WORK)"
    exit 1
fi
rm -rf "$WORK"
log "Clean. Findings (if any were fixed this round) -> BUGLOG.md."
