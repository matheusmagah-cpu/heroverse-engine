#!/usr/bin/env bash
# E60: a GitHub release asset must be < 2 GiB; pilot-009's 16-minute 1440p render (2.1 GB) could not be stored and the
# whole render was lost. Long renders are stored as parts of at most 1.9 GiB and rejoined, hash-verified, on download.
#   release_video.sh put FILE NAME          upload FILE as NAME, or as NAME.part01, NAME.part02, ... when too large
#   release_video.sh get NAME SHA256 OUT    download NAME (or its parts), rejoin, verify the hash
#   release_video.sh del NAME               delete NAME and any parts
set -euo pipefail
: "${REPO:=${GITHUB_REPOSITORY:?}}"
ASSETS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/assets.sh"  # E85: several releases, newest first
PART=${RELEASE_PART_BYTES:-$((1900 * 1024 * 1024))}  # override only in tests
cmd=$1; shift
case "$cmd" in
  put)
    file=$1; name=$2; dir=$(mktemp -d)
    if [ "$(stat -c %s "$file")" -lt "$PART" ]; then
      cp "$file" "$dir/$name"
    else
      split -b "$PART" -d -a 2 --numeric-suffixes=1 "$file" "$dir/$name.part"
    fi
    bash "$ASSETS" upload "$dir"/* --repo "$REPO" --clobber
    rm -rf "$dir" ;;
  get)
    name=$1; sha=$2; out=$3; dir=$(mktemp -d)
    if ! bash "$ASSETS" download --repo "$REPO" --pattern "$name" -D "$dir" 2>/dev/null; then
      bash "$ASSETS" download --repo "$REPO" --pattern "$name.part*" -D "$dir"
    fi
    cat $(ls "$dir"/* | sort) > "$out"
    rm -rf "$dir"
    echo "$sha  $out" | sha256sum -c - ;;
  del)
    name=$1
    for a in $(bash "$ASSETS" names --repo "$REPO" | grep -E "^${name//./\\.}(\.part[0-9]+)?$" | sort -u); do
      bash "$ASSETS" delete "$a" --repo "$REPO"
    done ;;
  *) echo "usage: release_video.sh put|get|del ..." >&2; exit 2 ;;
esac
