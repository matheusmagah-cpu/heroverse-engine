#!/usr/bin/env bash
# E102: render_pilot.sh fetched ~150 release assets one after another (~1.5 s each, 4 min of a 20-minute smoke run).
# fetch_assets.sh LIST REPO [JOBS]: every line of LIST is "asset<TAB>destination<TAB>sha256"; each asset is downloaded
# with assets.sh and hash-checked, JOBS at a time (default 4). Any download or hash failure fails the whole call
# (xargs exits non-zero), so nothing reaches the render unverified. ASSETS may point at another downloader (tests).
set -euo pipefail
list=${1:?usage: fetch_assets.sh LIST REPO [JOBS]}; repo=${2:?usage: fetch_assets.sh LIST REPO [JOBS]}; jobs=${3:-4}
[[ "$jobs" =~ ^[1-9][0-9]?$ ]] || { echo "FETCH_JOBS_REFUSED $jobs"; exit 1; }
export ASSETS="${ASSETS:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/assets.sh}" FETCH_REPO="$repo"
one() {
  local asset=$1 dest=$2 sha=$3
  [[ "$sha" =~ ^[0-9a-f]{64}$ ]] || { echo "FETCH_SHA_REFUSED $asset"; return 1; }
  bash "$ASSETS" download --repo "$FETCH_REPO" --pattern "$asset" -O "$dest" --clobber || { echo "FETCH_FAILED $asset"; return 1; }
  echo "$sha  $dest" | sha256sum -c - || { echo "FETCH_HASH_MISMATCH $asset"; return 1; }
}
export -f one
n=$(grep -c . "$list" || true)
[ "${n:-0}" -gt 0 ] || { echo "FETCH_LIST_EMPTY"; exit 0; }
awk -F'\t' 'NF != 3 || $1 == "" || $2 == "" { bad = 1 } END { exit bad }' "$list" || { echo "FETCH_LIST_MALFORMED"; exit 1; }
# xargs exits 123 when any invocation failed; the line's three fields become the function's arguments
tr '\t' '\n' < "$list" | xargs -d '\n' -n 3 -P "$jobs" bash -c 'one "$@"' _
echo "FETCHED $n"
