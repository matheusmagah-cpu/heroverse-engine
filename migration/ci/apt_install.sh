#!/usr/bin/env bash
# E55: runs 39823760082 and 40000227373 hung on the hosted apt mirror list. Every engine apt install goes through this
# one script: the official Ubuntu origins (same signed sources), per-request timeouts and a timeout on each command,
# so a stalled mirror fails the step instead of hanging it.
#   apt_install.sh PKG...      env: APT_UPDATE_TIMEOUT (default 180s), APT_INSTALL_TIMEOUT (default 300s),
#                                   APT_SOURCES (default /etc/apt/sources.list.d/ubuntu.sources)
set -euo pipefail
[ $# -gt 0 ] || { echo "APT_NO_PACKAGES"; exit 2; }
for p in "$@"; do
  [[ "$p" =~ ^[a-z0-9][a-z0-9.+-]*$ ]] || { echo "APT_PACKAGE_REFUSED $p"; exit 2; }
done
src_in=${APT_SOURCES:-/etc/apt/sources.list.d/ubuntu.sources}
opts=(-o APT::Get::List-Cleanup=0 -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)
if [ -f "$src_in" ]; then
  src="${RUNNER_TEMP:-/tmp}/heroverse-ubuntu.sources"
  sed -e 's#mirror+file:/etc/apt/apt-mirrors.txt#https://archive.ubuntu.com/ubuntu/#g' \
      -e 's#mirror+file:/etc/apt/apt-mirrors-security.txt#https://security.ubuntu.com/ubuntu/#g' "$src_in" > "$src"
  opts=(-o "Dir::Etc::sourcelist=$src" -o Dir::Etc::sourceparts=- "${opts[@]}")
else
  echo "APT_SOURCES_DEFAULT $src_in missing: the image's own sources, still with timeouts"
fi
timeout "${APT_UPDATE_TIMEOUT:-180s}" sudo apt-get "${opts[@]}" update -qq
timeout "${APT_INSTALL_TIMEOUT:-300s}" sudo apt-get "${opts[@]}" install -y -qq --no-install-recommends "$@" >/dev/null
