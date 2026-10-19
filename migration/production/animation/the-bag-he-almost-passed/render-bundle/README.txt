Animation bundle v2: original armature-skinned humanoids, 24 unique fps.

Requires Blender 4.3.2, Eevee Next and a working headless EGL context. No
network, downloaded assets, fonts or packages are used by the renderer.
Set RENDER_OUT to a writable directory; caches and renders stay under it.
For Blender startup caches also set XDG_CACHE_HOME=$RENDER_OUT/cache and
MESA_SHADER_CACHE_DIR=$RENDER_OUT/cache/mesa before invoking Blender.

RENDER_OUT=/work/output blender -b -t 0 --python production.py -- master 0 24 --timing timing.json
RENDER_OUT=/work/output blender -b -t 0 --python production.py -- vertical 0 24 --timing timing.json --shorts shorts-map.json

START is inclusive, END exclusive. Master output hd-frames/%05d.png is
1920x1080. Vertical output vertical-frames/<short>-%05d.png is 1080x1920,
with independent perspective cameras, no cropping or upscaling. Portrait
chunk indices enumerate short1 then short2, concatenated, while filename
indices restart at zero within each Short. Output time is mapped through
source spans at speed1, rendered at fractional source-frame times. Total
frames = round(total_s*24), avoiding cumulative per-span rounding drift.
Each frames-<kind>-<START>-<END>.json maps global chunk indices to PNG SHA256.
Do not reuse old 10fps output. The previous invocation below is retained
only as the issue card's literal interface anchor, and is now incomplete:
RENDER_OUT=/work/output blender -b -t 8 --python production.py -- master 0 100
It must receive --timing. No legacy implicit or estimated timeline is used.

Timing and Short spans come from the measured voice timeline, as specified
in #191. Development render samples may use explicitly labelled synthetic
timing fixtures; those are not production timing or voice qualification.
Models use unified remeshed tailored surfaces, weighted armature deformation,
breathing and gait, head turns, eyes/blinks and expression shape keys.
The environment reuses original scene geometry; character designs are new.

Assembly CLI (from repository):
python3 assemble.py WORK SCENES TIMING SHORTS_MAP MUSIC OUT
WORK contains hd-frames/, vertical-frames/, voice.wav and timeline.json.
Uses ffmpeg, ffprobe and system fonts-dejavu-core. SRT text and timings
retain the exact source sentences. Vertical captions display simultaneous
lines of 1-5 words, each bounded by its complete source sentence, rather
than inventing per-word timestamps. Source SRT retains complete sentences.
Cards use scenes.json overlay text, confined to the spoken sentence.
Music is mixed 16dB below the voice's measured integrated mean level, then
two-pass loudness normalization targets -15LUFS / -1.5dBTP before AAC.
This integrated separation does not prove per-instant ducking. Outputs
must still pass frozen QA, actual audio measurements and watched review.

No claim of full visual approval or end-to-end qualification is made by
this bundle. Use PR evidence for actual acceptance status and measurements.
