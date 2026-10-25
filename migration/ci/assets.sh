#!/usr/bin/env bash
# E85: a GitHub release holds at most 1000 assets; v0.0.0-cloud-assets-20261013 filled up on 2026-10-25 and every new
# upload (footage run 40218507819) failed with HTTP 422 file_count. The engine's assets now live in several releases,
# newest first: uploads go to the newest (created when missing), reads try the newest first and fall back to older ones.
# When the newest is nearly full, add a new tag at the front of TAGS (a warning is printed past WARN_AT).
#   assets.sh download ARGS...       gh release download ARGS (e.g. --pattern NAME -O FILE), first release that has it
#   assets.sh upload FILES... ARGS   gh release upload into the newest release
#   assets.sh names                  every asset name, all releases (one per line)
#   assets.sh which NAME             the tag of the newest release holding NAME
#   assets.sh delete NAME ARGS       delete NAME from every release holding it
#   assets.sh newest                 the tag uploads go to
#   assets.sh tags                   every tag, newest first
# --repo REPO may be passed anywhere (default $GITHUB_REPOSITORY).
set -euo pipefail
TAGS=(v0.0.0-cloud-assets-20261025 v0.0.0-cloud-assets-20261013)
WARN_AT=950
cmd=${1:?usage: assets.sh download|upload|names|which|delete|newest|tags ...}; shift
repo=${GITHUB_REPOSITORY:-}; args=()
while [ $# -gt 0 ]; do
  if [ "$1" = "--repo" ]; then repo=$2; shift 2; else args+=("$1"); shift; fi
done
: "${repo:?--repo or GITHUB_REPOSITORY}"
missing() { grep -qiE "no assets match|release not found|not found" <<<"$1"; }

case "$cmd" in
  download)
    for t in "${TAGS[@]}"; do
      if err=$(gh release download "$t" --repo "$repo" "${args[@]}" 2>&1 >/dev/null); then exit 0; fi
      missing "$err" || { echo "$err" >&2; exit 1; }   # a real error is never hidden behind an older copy
    done
    echo "no assets match the file pattern in ${TAGS[*]}" >&2; exit 1 ;;
  upload)
    t=${TAGS[0]}
    if ! gh release view "$t" --repo "$repo" --json tagName >/dev/null 2>&1; then
      gh release create "$t" --repo "$repo" --prerelease --target main --title "HeroVerse — private cloud assets ($t)" \
        --notes "Engine assets continued from ${TAGS[1]} (E85: 1000 assets per release)." >/dev/null 2>&1 ||
        gh release view "$t" --repo "$repo" --json tagName >/dev/null   # a parallel run may have just created it
    fi
    gh release upload "$t" "${args[@]}" --repo "$repo"
    n=$(gh release view "$t" --repo "$repo" --json assets --jq '.assets | length' 2>/dev/null || echo 0)
    if [ "${n:-0}" -ge "$WARN_AT" ]; then echo "::warning::ASSET_RELEASE_NEARLY_FULL $t has $n of 1000 assets: add a new tag to migration/ci/assets.sh (E85)"; fi ;;
  names)
    for t in "${TAGS[@]}"; do
      gh release view "$t" --repo "$repo" --json assets --jq '.assets[].name' 2>/dev/null || true
    done ;;
  which)
    name=${args[0]:?}
    for t in "${TAGS[@]}"; do
      if gh release view "$t" --repo "$repo" --json assets --jq '.assets[].name' 2>/dev/null | grep -qxF -- "$name"; then
        echo "$t"; exit 0
      fi
    done
    echo "ASSET_NOT_FOUND $name" >&2; exit 1 ;;
  delete)
    name=${args[0]:?}; found=0
    for t in "${TAGS[@]}"; do
      if gh release delete-asset "$t" "$name" --repo "$repo" -y >/dev/null 2>&1; then found=1; fi
    done
    [ "$found" = 1 ] || { echo "ASSET_NOT_FOUND $name" >&2; exit 1; } ;;
  newest) echo "${TAGS[0]}" ;;
  tags) printf '%s\n' "${TAGS[@]}" ;;
  *) echo "usage: assets.sh download|upload|names|which|delete|newest|tags ..." >&2; exit 2 ;;
esac
