#!/bin/bash
# usage: lease_tmp.sh active|idle "<next_action>"
set -e
state=$1; next=$2
git fetch -q origin claude/shared-executor-control
head=$(git rev-parse FETCH_HEAD)
tree=$(git rev-parse FETCH_HEAD^{tree})
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if [ "$state" = active ]; then
  owner='"claude"'; exp=$(date -u -d '+50 min' +%Y-%m-%dT%H:%M:%SZ)
else
  owner=null; exp=$now
fi
main=$(git rev-parse origin/main)
msg=$(printf 'HEROVERSE_EXECUTOR_LEASE_V1\n{"schema":"heroverse-executor-lease-v1","owner":%s,"run_id":"claude-short09-round2-20261031","state":"%s","renewed_at":"%s","expires_at":"%s","task":"genesis-09-short round 2 (Buzzy track): Pavo k-close talking, Buzzy clips","base_main_sha":"%s","next_action":"%s"}' "$owner" "$state" "$now" "$exp" "$main" "$next")
new=$(git commit-tree "$tree" -p "$head" -m "$msg")
git push -q origin "$new:refs/heads/claude/shared-executor-control"
git fetch -q origin claude/shared-executor-control
echo "ref now $(git rev-parse FETCH_HEAD) (mine $new) state=$state expires=$exp"
