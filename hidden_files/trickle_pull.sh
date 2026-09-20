#!/bin/bash
# trickle_pull.sh — rate-limited Docker image fetch (fallback for flaky pulls).
#
# Why this exists: `docker pull` has no bandwidth limit, and `trickle`
# (LD_PRELOAD) cannot hook Go's statically-linked binaries, so a true
# "trickle" pull is done by hand: fetch each blob through the registry HTTP
# API with curl --limit-rate, assemble a docker-load tarball, `docker load`.
#
# Usage: trickle_pull.sh <repository> <tag> [rate] [--probe]
#   rate: curl --limit-rate value, e.g. 500K, 1M (default 1M)
#   --probe: only fetch token+manifest, print total size + ETA, then exit
set -u
REPO="${1:?need repository}"; TAG="${2:?need tag}"; RATE="${3:-1M}"
PROBE="${4:-}"
LOG=~/workspace/forum-stack/hidden_files/docker_pulls_trickle_2026-09-19.log
W=~/workspace/forum-stack/hidden_files/trickle/${REPO//\//_}_${TAG}
mkdir -p "$W/blobs"
log(){ echo "[$(date -u '+%F %T UTC')] trickle[$REPO:$TAG] $*" >> "$LOG"; echo "[$(date -u '+%F %T UTC')] trickle[$REPO:$TAG] $*"; }

get_token(){
  for i in $(seq 1 5); do
    T=$(curl -s --max-time 30 \
      "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${REPO}:pull" \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
    [ -n "$T" ] && { echo "$T"; return 0; }
    sleep 10
  done
  return 1
}

# --- fetch manifest (follows multi-arch list -> linux/amd64) ---
TOKEN="$(get_token)" || { log "FATAL: no token"; exit 1; }
MJ="$(curl -s --max-time 60 -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json" \
  "https://registry-1.docker.io/v2/${REPO}/manifests/${TAG}")"
SUB="$(echo "$MJ" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if 'manifests' in d:
    for m in d['manifests']:
        p=m.get('platform',{})
        if p.get('os')=='linux' and p.get('architecture')=='amd64':
            print(m['digest']); break
" 2>/dev/null)"
if [ -n "$SUB" ]; then
  MJ="$(curl -s --max-time 60 -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
    "https://registry-1.docker.io/v2/${REPO}/manifests/${SUB}")"
fi
echo "$MJ" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert 'layers' in d, 'manifest fetch failed: '+str(d)[:120]
open('$W/config_digest.txt','w').write(d['config']['digest'])
ls=[(l['digest'],l['size']) for l in d['layers']]
open('$W/layers.txt','w').write('\n'.join(x[0] for x in ls)+'\n')
open('$W/layer_sizes.txt','w').write('\n'.join(str(x[1]) for x in ls)+'\n')
total=sum(x[1] for x in ls)+d['config']['size']
open('$W/total_bytes.txt','w').write(str(total))
print('LAYERS',len(ls),'TOTAL_BYTES',total)
" || { log "FATAL: manifest parse failed"; exit 1; }
read -r LAYERS TOTAL < <(echo "$MJ" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(len(d['layers']), sum(l['size'] for l in d['layers'])+d['config']['size'])")

RATE_BPS=$(python3 -c "
r='$RATE'.strip().upper(); m={'K':1024,'M':1024**2,'G':1024**3}
print(int(float(r[:-1])*m[r[-1]]) if r[-1] in m else int(r))")
ETA_S=$(( TOTAL / RATE_BPS ))
log "manifest OK: $LAYERS layers, $TOTAL bytes (~$((TOTAL/1048576)) MB); rate $RATE -> ETA ~$((ETA_S/60)) min"

[ "$PROBE" = "--probe" ] && { log "probe done"; exit 0; }

# --- download blobs (config + layers), resumable, rate-limited ---
dl_blob(){
  local digest="$1" expect="$2" hex="${1#sha256:}" out="$W/blobs/$hex"
  for att in $(seq 1 8); do
    local size=0; [ -f "$out" ] && size=$(stat -c%s "$out")
    if [ "$size" -eq "$expect" ]; then log "have $hex ($expect bytes)"; return 0; fi
    local TK; TK="$(get_token)" || { sleep 20; continue; }
    log "blob $hex attempt $att/8 (have $size/$expect bytes)"
    if curl -sL --max-time 600 --limit-rate "$RATE" -C - \
        -H "Authorization: Bearer $TK" \
        -o "$out" "https://registry-1.docker.io/v2/${REPO}/blobs/${digest}" 2>>"$LOG"; then
      size=$(stat -c%s "$out")
      [ "$size" -eq "$expect" ] && { log "blob $hex complete"; return 0; }
      log "blob $hex short: $size/$expect — retrying"
    else
      log "blob $hex curl failed — retrying in 20s"
    fi
    sleep 20
  done
  log "FATAL: blob $hex failed 8 attempts"; return 1
}

CFG_DIGEST="$(cat "$W/config_digest.txt")"
CFG_SIZE=$(echo "$MJ" | python3 -c "import json,sys; print(json.load(sys.stdin)['config']['size'])")
dl_blob "$CFG_DIGEST" "$CFG_SIZE" || exit 1
i=0
while read -r digest; do
  i=$((i+1)); size=$(sed -n "${i}p" "$W/layer_sizes.txt")
  dl_blob "$digest" "$size" || exit 1
done < "$W/layers.txt"

# --- assemble docker-load tarball ---
log "all blobs fetched; assembling image tarball"
IMGDIR="$W/image"; rm -rf "$IMGDIR"; mkdir -p "$IMGDIR"
cfg_hex="${CFG_DIGEST#sha256:}"
cp "$W/blobs/$cfg_hex" "$IMGDIR/$cfg_hex.json"
python3 - "$IMGDIR" "$cfg_hex" "$REPO" "$TAG" "$W/layers.txt" << 'PYEOF'
import json,sys
imgdir,cfg,repo,tag,lf=sys.argv[1:6]
layers=[l.strip().split(':',1)[1]+'/layer.tar' for l in open(lf) if l.strip()]
json.dump([{"Config":cfg+".json","RepoTags":[repo+":"+tag],"Layers":layers}],
          open(imgdir+'/manifest.json','w'))
PYEOF
while read -r digest; do
  hex="${digest#sha256:}"; mkdir -p "$IMGDIR/$hex"
  cp "$W/blobs/$hex" "$IMGDIR/$hex/layer.tar"
done < "$W/layers.txt"
tar -cf "$W/image.tar" -C "$IMGDIR" .
log "loading into docker"
docker load -i "$W/image.tar" 2>&1 | tail -2 >> "$LOG"
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep "^${REPO}:${TAG} " >> "$LOG" \
  && log "TRICKLE COMPLETE: $REPO:$TAG" || { log "FATAL: docker load unverified"; exit 1; }
