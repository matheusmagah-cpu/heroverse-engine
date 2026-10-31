#!/bin/bash
# usage: wait_tmp.sh <branch>
for i in $(seq 1 55); do
  r=$(gh api repos/matheusmagah-cpu/heroverse-engine/commits/$1/check-runs --jq '[.check_runs[]|(.conclusion // .status)]|join(",")')
  case "$r" in *in_progress*|*queued*|"") sleep 10;; *) break;; esac
done
echo "$r"
