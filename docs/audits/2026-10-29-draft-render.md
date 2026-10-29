# Offline draft rendering: E219

Manual code/security review by the ChatGPT Codex session. The Claude-hosted
pr-review-toolkit and verified-security-sweep plugins are unavailable here;
neither plugin execution nor audiovisual approval is claimed. FFmpeg command
changes received the ffmpeg-expert review required by CLAUDE.md.

The repair applies to the offline editing renderer, not the publication gate.
The legacy runner's observed QUEUE_EMPTY is accurate for its pilot queue. Bible
plans have a separate qualified-production handoff in the existing heartbeat;
an unqualified editing draft must not be routed around that handoff.

The new CLI accepts local, hash-bound media. Input protocols are limited to
file/pipe; there is no provider or credential access. Image reuse is explicit
and requires an actual image input. No source qualification is inferred from it.
The output and cache are locked; overlap with inputs is refused. Consumers use
sealed bytes, not mutable filenames previously validated. MP4 output is seekable
and finalized before sealing, preserving timestamps without a fixed offset.

Final validation decodes the complete file and checks the video stream's own
duration, start, geometry and decoded frame count. Long audio cannot conceal a
short picture. The AAC copy route compares payload hashes, packet timing and
priming metadata. Atomic replacement happens only after validation. Matching
recipes can reuse final outputs; valid cached segments survive an interrupted
render. Corrupt cache or uncertain receipts do not qualify as completed output.

The PR adds the regression suite to existing PR checks. Permissions, secrets,
workflow dispatches, publication policy and frozen criteria are unchanged.
No private package, account metrics, Library identifiers or media are committed.
The existing supervisor's private package operation is configured separately,
after the real-media render succeeds; no new clock or public upload is introduced.

Regression evidence: the initial real-media negative fixture has a 0.6-second
container and only 0.2 seconds of video. A container-only guard accepted it and
the new test failed before the fix. The corrected validator rejects it. Ten
focused tests also cover sealed-input mutation, exact AAC copying, idempotent
reuse, selective cache recovery, locks, overlap, existing still opt-in and an
actual FFmpeg failure preserving the prior file.

Canonical local checks: all 86 suites passed in 66.87 seconds. OpenCV was supplied
from an isolated dependency directory; no test or production assertion was changed
to accommodate the environment. No pilot input was changed. `git diff --check` passed.
