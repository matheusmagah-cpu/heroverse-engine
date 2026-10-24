#!/usr/bin/env bash
# One full render of a pilot: voice, images, figure, assembly, Shorts input handoff
# (selection/review deferred until the long qualifies), QA, package, release upload and the
# evidence commit. Single source of truth for every runner: the private repo's
# own workflow and the public execution repo (more CPU, no minute cap) both run
# this script on a checkout of the private repo.
# env: PILOT, TAG, ENGINE_REPO (owner/repo of the private engine), GH_TOKEN,
#      RUN_LABEL, T (scratch dir); no Shorts model calls in this renderer
set -euo pipefail
case "$PILOT" in pilot-[0-9][0-9][0-9]) ;; *) echo "INVALID_PILOT"; exit 1;; esac
T="${T:-${RUNNER_TEMP:-/tmp}}"; ROOT="$(pwd)"; QA_FAILED=""
stage() { echo "::group::$1"; date -u +%H:%M:%S; }
end() { echo "::endgroup::"; }
# On the public runner (PUBLIC_LOGS=1) command output (titles, script text, hooks) goes to a private log
# that is uploaded to the private release; the public log shows only stage names, times and pass/fail.
LOG="$T/render-private.log"; : > "$LOG"
q() { if [ "${PUBLIC_LOGS:-0}" = 1 ]; then "$@" >>"$LOG" 2>&1 || { for a in "$@"; do case "$a" in *.py) echo "FAILED: $(basename "$a")";; esac; done; return 1; }; else "$@"; fi; }
upload_log() { [ "${PUBLIC_LOGS:-0}" = 1 ] && gh release upload "$TAG" "$LOG#$PILOT-render-log-${RUN_LABEL// /-}.txt" --repo "$ENGINE_REPO" --clobber >/dev/null 2>&1 || true; }
trap upload_log EXIT

stage "Free runner disk (unused preinstalled SDKs) and record space"
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL 2>/dev/null || true
df -h / "$T" | tail -n +1
end

stage "Tools and pinned runtimes"
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends ffmpeg espeak-ng fonts-dejavu-core >/dev/null
python3 -m venv "$T/voice"; "$T/voice/bin/pip" install --disable-pip-version-check -q 'kokoro-onnx==0.4.9' 'onnxruntime==1.20.1' 'numpy==2.2.6' 'espeakng-loader==0.2.4' 'soundfile==0.13.1'
python3 -m venv "$T/qa"; "$T/qa/bin/pip" install --disable-pip-version-check -q ai-edge-litert==2.3.0 faster-whisper==1.2.1
python3 -m venv "$T/cut"; "$T/cut/bin/pip" install --disable-pip-version-check -q 'rembg==2.0.59' 'onnxruntime==1.20.1' 'pillow==11.0.0'
python3 -m venv "$T/cine"; "$T/cine/bin/pip" install --disable-pip-version-check -q 'numpy==2.2.6' 'opencv-python-headless==4.10.0.84' 'onnxruntime==1.20.1'
mkdir -p "$T/models"
curl -fsSL --retry 3 -o "$T/models/depth-anything-v2-small.onnx" https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx
sha256sum "$T/models/depth-anything-v2-small.onnx"
export HERO_DEPTH_MODEL="$T/models/depth-anything-v2-small.onnx"
end

stage "Verified source, pinned voice model, narration"
q python3 -I -B migration/production/pilot_render.py prepare "$T/work" HeroVerse_Linux_Source_Ready_20261013_v2.zip
q "$T/voice/bin/python" -I -B migration/production/pilot_render.py voice "$T/work" "migration/production/$PILOT/script.json"
end

stage "Owned music and generated images from the private release"
mkdir -p "$T/in/img"
gh release download "$TAG" --repo "$ENGINE_REPO" --pattern original-rest-music.lossless.flac -O "$T/in/original-rest-music.lossless.flac" --clobber
echo "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c  $T/in/original-rest-music.lossless.flac" | sha256sum -c -
for meta in migration/production/$PILOT/images/*.json; do
  id=$(basename "$meta" .json)
  read -r asset sha < <(python3 -I -c "import json,sys;m=json.load(open(sys.argv[1]));print(m['release_asset'],m['sha256'])" "$meta")
  gh release download "$TAG" --repo "$ENGINE_REPO" --pattern "$asset" -O "$T/in/img/$id.png" --clobber
  echo "$sha  $T/in/img/$id.png" | sha256sum -c -
  cp "$meta" "$T/in/img/$id.json"
done
# v4 (owner, 2026-10-23): licensed real footage from the vetted library, verified by hash like the images
mkdir -p "$T/in/footage"
for id in $(python3 -I -c "import json,sys;print(' '.join(json.load(open(sys.argv[1])).get('footage') or []))" "migration/production/$PILOT/script.json"); do
  meta="migration/production/footage/library/$id.json"
  read -r asset sha < <(python3 -I -c "import json,sys;m=json.load(open(sys.argv[1]));print(m['release_asset'],m['sha256'])" "$meta")
  gh release download "$TAG" --repo "$ENGINE_REPO" --pattern "$asset" -O "$T/in/footage/$id.mp4" --clobber
  echo "$sha  $T/in/footage/$id.mp4" | sha256sum -c -
  cp "$meta" "$T/in/footage/$id.json"
done
CRITERIA=migration/production/qa_criteria_v3.json
if ls "$T"/in/footage/*.mp4 >/dev/null 2>&1; then
  CRITERIA=migration/production/qa_criteria_v4.json
  export HERO_FRAME=2560x1440   # v4: never below 1440p (owner, 2026-10-23)
fi
fig=$(python3 -I -c "import json,sys;print(json.load(open(sys.argv[1]))['figure'])" "migration/production/$PILOT/script.json")
q "$T/cut/bin/python" -I -B migration/production/imagegen/cutout.py "$T/in/img/$fig.png" "$T/in/img/$fig.json" "$T/in/figure.png"
end

stage "Assemble"
q "$T/cine/bin/python" -I -B migration/production/still_render.py assemble "$T/work" "migration/production/$PILOT/script.json" "$T/in/img" "$T/in/figure.png" "$T/in/original-rest-music.lossless.flac" "$T/in/footage"
end

df -h "$T" | tail -1
stage "Preserve Shorts inputs for after long qualification"
mkdir -p "$T/work/shorts"
# Always hand off: long QA and designated review must finish before Shorts spend quota.
HANDOFF=1
ffmpeg -v error -y -i "$T/work/voice.wav" -c:a flac "$T/voice.flac"
vsha=$(sha256sum "$T/voice.flac" | cut -d' ' -f1); fsha=$(sha256sum "$T/in/figure.png" | cut -d' ' -f1)
cp "$T/voice.flac" "$T/$PILOT-voice-sha256-$vsha.flac"; cp "$T/in/figure.png" "$T/$PILOT-figure-sha256-$fsha.png"
gh release upload "$TAG" "$T/$PILOT-voice-sha256-$vsha.flac" "$T/$PILOT-figure-sha256-$fsha.png" --repo "$ENGINE_REPO" --clobber
printf '{"voice_asset": "%s", "voice_sha256": "%s", "figure_asset": "%s", "figure_sha256": "%s", "render": "%s"}\n' \
  "$PILOT-voice-sha256-$vsha.flac" "$vsha" "$PILOT-figure-sha256-$fsha.png" "$fsha" "${RUN_LABEL:-run}" > "$T/shorts-inputs.json"
end

stage "QA against frozen criteria"
( cd "$T/models"
  gh release download "$TAG" --repo "$ENGINE_REPO" --pattern 'yamnet-classification-tflite-v1-sha256-*.tflite' -O yamnet.tflite --clobber
  echo "10c95ea3eb9a7bb4cb8bddf6feb023250381008177ac162ce169694d05c317de  yamnet.tflite" | sha256sum -c -
  gh release download "$TAG" --repo "$ENGINE_REPO" --pattern HeroVerse_ASR_base_en_preservado.zip --clobber
  echo "78634f845a29c523d117a29a1a14b293220787f5ede2c6c0f33a9b06c2f805cb  HeroVerse_ASR_base_en_preservado.zip" | sha256sum -c -
  "$T/qa/bin/python" -I -c "import sys; from pathlib import Path; sys.path.insert(0, '$ROOT/migration'); import second_opening_asr as a; a.extract_model(Path('HeroVerse_ASR_base_en_preservado.zip'), Path('whisper'))" )
q "$T/qa/bin/python" -I -B migration/production/qa_pilot.py "$T/work/pilot.mp4" "$T/work/manifest.json" \
  "migration/production/$PILOT/script.json" "$CRITERIA" \
  "$T/models/yamnet.tflite" "$T/models/whisper" "$T/work/qa.json" || QA_FAILED=1
end

stage "Package (no upload to YouTube) and inspection sheets"
q python3 -I -B migration/production/package_pilot.py "$T/work" "migration/production/$PILOT/script.json" "$T/work/package"
# R16 thumbnail ruler (Pillow and NumPy come with the cut-out venv)
"$T/cut/bin/python" -I -B migration/production/thumb_check.py "$T/work/package/thumbnail.jpg" "$T/work/package/thumbnail_check.json" || QA_FAILED=1
mkdir -p "migration/production/$PILOT/inspection"
d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$T/work/pilot.mp4")
n=$(python3 -c "import math;print(math.ceil($d/20))")
ffmpeg -v error -y -i "$T/work/pilot.mp4" -vf "fps=1/20,scale=480:270,tile=4x$(( (n + 3) / 4 ))" -frames:v 1 -q:v 4 "migration/production/$PILOT/inspection/pilot-contact-sheet.jpg"
ffmpeg -v error -y -ss 0 -t 40 -i "$T/work/pilot.mp4" -vf "fps=1/2.5,scale=480:270,tile=4x4" -frames:v 1 -q:v 4 "migration/production/$PILOT/inspection/opening-sheet.jpg"
ffmpeg -v error -y -i "$T/in/figure.png" -vf "scale=-1:540,pad=iw+40:ih+40:20:20:color=0x808080" "migration/production/$PILOT/inspection/figure-cutout.jpg"
end

stage "Preserve render privately and record evidence"
sha=$(sha256sum "$T/work/pilot.mp4" | cut -d' ' -f1)
REPO="$ENGINE_REPO" bash migration/ci/release_video.sh put "$T/work/pilot.mp4" "$PILOT-sha256-$sha.mp4"  # parts when > 1.9 GiB (E60)
if [ -f "$T/work/package/thumbnail.jpg" ]; then cp "$T/work/package/thumbnail.jpg" "$T/$PILOT-thumbnail.jpg"; gh release upload "$TAG" "$T/$PILOT-thumbnail.jpg" --repo "$ENGINE_REPO" --clobber; fi
mkdir -p "migration/production/$PILOT/out" "migration/production/$PILOT/shorts"
cp "$T/work/manifest.json" "$T/work/timeline.json" "$T/work/captions.ass" "migration/production/$PILOT/out/"
cp "$T/work/qa.json" "migration/production/$PILOT/out/qa.json" || true
cp "$T/work/package/package.json" "migration/production/$PILOT/out/package.json" || true
cp "$T/work/package/thumbnail.jpg" "migration/production/$PILOT/inspection/thumbnail.jpg" || true
cp "$T/work/package/thumbnail_check.json" "migration/production/$PILOT/out/thumbnail_check.json" || true
if [ -n "$HANDOFF" ]; then
  # stale Shorts of an earlier render must never be published with this one
  rm -f "migration/production/$PILOT/shorts/"*.json "migration/production/$PILOT/shorts/"*-frame.jpg
  cp "$T/shorts-inputs.json" "migration/production/$PILOT/shorts/inputs.json"
fi
cp "$T/work/shorts/shorts.json" "$T/work/shorts/selection.json" "migration/production/$PILOT/shorts/" 2>/dev/null || true
for s in "$T"/work/shorts/short-*.mp4; do
  [ -f "$s" ] || continue
  ssha=$(sha256sum "$s" | cut -d' ' -f1); b=$(basename "$s" .mp4)
  cp "$s" "$T/$PILOT-$b-sha256-$ssha.mp4"
  gh release upload "$TAG" "$T/$PILOT-$b-sha256-$ssha.mp4" --repo "$ENGINE_REPO" --clobber
  ffmpeg -v error -y -ss 3 -i "$s" -frames:v 1 -vf scale=360:-1 "migration/production/$PILOT/shorts/$b-frame.jpg" || true
done
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A "migration/production/$PILOT/out" "migration/production/$PILOT/inspection" "migration/production/$PILOT/shorts"
git commit -q -m "Record $PILOT render, QA, package and inspection sheets (${RUN_LABEL:-run}; not published)"
git pull --rebase -q origin main && git push -q origin HEAD:main
end
test -z "$QA_FAILED"
