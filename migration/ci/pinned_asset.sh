#!/usr/bin/env bash
# E240: a pinned third-party file (model weights) is read from the engine's own release first, by its sha256, and
# from its original host only when the mirror does not hold it yet. episode.yml run 41244405674 died in its tools step
# because www.robots.ox.ac.uk refused every connection for syncnet_v2.model (curl exit 28 four times).
#   pinned_asset.sh fetch NAME SHA256 DEST URL   mirror asset NAME (assets.sh) else URL; DEST must hash to SHA256
#   pinned_asset.sh mirror NAME SHA256 URL       upload URL's bytes as NAME once, only when they hash to SHA256
# A mirror copy whose hash differs is never used and never hidden behind the original host: PINNED_ASSET_SHA_MISMATCH
# (fail closed). The original host's bytes are checked the same way. ASSETS may point at another downloader (tests).
set -euo pipefail
ASSETS="${ASSETS:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/assets.sh}"
cmd=${1:?usage: pinned_asset.sh fetch|mirror ...}; shift
check_sha() { [[ "$1" =~ ^[0-9a-f]{64}$ ]] || { echo "PINNED_ASSET_SHA_REFUSED $1" >&2; exit 2; }; }
hash_ok() { [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ]; }
from_url() {   # URL DEST: the original host, retried, with a bounded time per try
  curl -fsSL --retry 4 --retry-all-errors --connect-timeout 20 --max-time 300 -o "$2" "$1"
}
case "$cmd" in
  fetch)
    name=${1:?NAME}; sha=${2:?SHA256}; dest=${3:?DEST}; url=${4:?URL}; check_sha "$sha"
    rm -f "$dest"
    if bash "$ASSETS" download --pattern "$name" -O "$dest" --clobber 2>/dev/null; then
      hash_ok "$dest" "$sha" || { rm -f "$dest"; echo "PINNED_ASSET_SHA_MISMATCH mirror $name" >&2; exit 1; }
      echo "PINNED_ASSET_FROM_MIRROR $name"; exit 0
    fi
    echo "::warning::PINNED_ASSET_NOT_MIRRORED $name: reading $url (dispatch pinned-assets.yml once to mirror it)"
    rm -f "$dest"
    from_url "$url" "$dest" || { rm -f "$dest"; echo "PINNED_ASSET_UNAVAILABLE $name (mirror and $url)" >&2; exit 1; }
    hash_ok "$dest" "$sha" || { rm -f "$dest"; echo "PINNED_ASSET_SHA_MISMATCH origin $name" >&2; exit 1; }
    echo "PINNED_ASSET_FROM_ORIGIN $name" ;;
  mirror)
    name=${1:?NAME}; sha=${2:?SHA256}; url=${3:?URL}; check_sha "$sha"
    if bash "$ASSETS" which "$name" >/dev/null 2>&1; then echo "PINNED_ASSET_ALREADY_MIRRORED $name"; exit 0; fi
    d=$(mktemp -d); trap 'rm -rf "$d"' EXIT
    from_url "$url" "$d/$name" || { echo "PINNED_ASSET_UNAVAILABLE $name ($url)" >&2; exit 1; }
    hash_ok "$d/$name" "$sha" || { echo "PINNED_ASSET_SHA_MISMATCH origin $name" >&2; exit 1; }
    bash "$ASSETS" upload "$d/$name"
    echo "PINNED_ASSET_MIRRORED $name" ;;
  *) echo "usage: pinned_asset.sh fetch|mirror ..." >&2; exit 2 ;;
esac
