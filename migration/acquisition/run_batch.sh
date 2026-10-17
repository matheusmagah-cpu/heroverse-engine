#!/usr/bin/env bash
# Sequential batch of reference windows. For each "VIDEO:START:END": reserve and
# push the claim, run one provider job, preserve media in the private release,
# profile it, then record and push the terminal state. A failure of one window
# is terminal for that window and does not stop the batch.
set -u
TAG=v0.0.0-cloud-assets-20261013
PY="$RUNNER_TEMP/venv/bin/python"
push() { git add migration/acquisition && git commit -q -m "$1" && { git pull --rebase -q origin main && git push -q origin HEAD:main; }; }
IFS=';' read -ra WINDOWS <<< "$1"
test "${#WINDOWS[@]}" -le 12 || { echo "BATCH_LIMIT_12"; exit 1; }
for window in "${WINDOWS[@]}"; do
  IFS=':' read -r VIDEO START END <<< "$window"
  rid="acq-$VIDEO-$START-$END-v1"; out="$RUNNER_TEMP/$rid"; asset=""
  echo "=== $rid"
  # Sync the ledger first: another run may have recorded claims since checkout.
  git pull --rebase -q origin main || { echo "LEDGER_SYNC_FAILED_STOP"; exit 1; }
  if ! python3 -I -B migration/acquisition/acquire_window.py reserve "$VIDEO" "$START" "$END"; then
    echo "RESERVE_REFUSED $rid (no effect)"; continue
  fi
  push "Reserve acquisition $rid before effect" || { echo "RESERVATION_NOT_DURABLE_STOP"; exit 1; }
  python3 -I -B migration/acquisition/acquire_window.py execute "$VIDEO" "$START" "$END" "$out" && ok=1 || ok=0
  if [ "$ok" = 1 ]; then
    sha=$(sha256sum "$out/native.mp4" | cut -d' ' -f1)
    asset="native-$VIDEO-$START-${END}s-sha256-$sha.mp4"
    cp "$out/native.mp4" "$RUNNER_TEMP/$asset"
    gh release upload "$TAG" "$RUNNER_TEMP/$asset" --repo "$GITHUB_REPOSITORY" && rm -f "$RUNNER_TEMP/$asset" || asset=""
    mkdir -p migration/acquisition/profiles
    "$PY" -I -B migration/diagnostics/av-profile/profile_openings.py "migration/acquisition/profiles/$rid.json" \
      "$RUNNER_TEMP/models/yamnet.tflite" "$RUNNER_TEMP/models/whisper" "$out/native.mp4" > /dev/null || echo "PROFILE_FAILED $rid"
  fi
  mkdir -p "$out" migration/acquisition/receipts
  receipt="$out/public-receipt.json"
  test -f "$receipt" || echo '{"status":"BLOCKED","effect_status":"NOT_SENT","failure_code":"EXECUTE_DID_NOT_RUN"}' > "$receipt"
  ASSET="$asset" python3 -I -c "import json,os,sys; r=json.load(open(sys.argv[1])); r['release_asset']=os.environ.get('ASSET') or None; json.dump(r, open(sys.argv[1],'w'), indent=2)" "$receipt"
  cp "$receipt" "migration/acquisition/receipts/$rid.json"
  python3 -I -B migration/acquisition/acquire_window.py finish "$VIDEO" "$START" "$END" "$receipt"
  rm -rf "$out"
  push "Record acquisition $rid terminal state" || echo "RECORD_PUSH_FAILED $rid"
done
