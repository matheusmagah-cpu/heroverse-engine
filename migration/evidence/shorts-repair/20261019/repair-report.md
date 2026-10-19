# pilot-012 Shorts repair

Baseline: commit `998e11b7598e31110e4f76619ab85833e23c5e0c`, run 39320311830.
The three baseline files passed technical QA. Watched scores were 7.5 and 6.8;
the third was NOT_REVIEWED_ProviderFailure. All remained publish=false.

## Root causes and repairs
- The selector accepted a clause ending in a colon as the opening and could
  reward a later hook instead of the spoken opening. The producer correctly
  hid that overlay. Both components now reject incomplete, context-dependent
  and over-3-second openings on measured sentence clocks.
- A period and the word “will” could score the start of a new reflection as a
  resolution. Selection now finishes the authored segment or an explicit
  resolving statement. This conservative text heuristic is not a creative review.
- ProviderFailure.code and diagnostic were discarded. The historical cause
  remains UNKNOWN: quota, outage and invalid request are not established.
  Bounded categorical HTTP/provider fields are now retained, never prose,
  raw bodies, URLs or credential values. The reviewer function AST is unchanged.
- The hook is an honest prefix of the first spoken line. Actual frame inspection
  exposed redundant hook/caption text; the optional overlay is now omitted when
  it repeats the first caption, retaining all captions and spoken content.
- The existing continuous 1.00→1.06 zoom, grade/film finish and slow scene changes
  are reused. A 0.5-second picture fade starts only after the last spoken word.
  No CTA, extra scene frequency, new model, threshold relaxation or publication.

## Tests and scope
22 producer/selection regressions and 4 diagnostic tests PASS. These cover the
three baseline openings, exact 3.000/3.001-second boundary, complete KJV, source
sentence bounds, actual candidates, duplicate-overlay omission and post-speech
fade. The original 35-script CI test list (including the new diagnostic suite)
passed locally. test_errors_register required registering that new suite;
SPEC v2 permits exactly that list addition, with no other workflow change.
CARD_OK and IN_SCOPE were checked. Final commit CI is reported on PR204.

## Real source media
The original archive SHA256 was verified:
fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10.
The unchanged pilot012 narration was regenerated locally through its existing
Kokoro adapter, am_michael at speed 0.85, using pinned assets:
- kokoro-v1.0.fp16.onnx: f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96
- voices-v1.0.bin: bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d
- Full voice: fc1a438aec0f4821b67223420dc1b6554b45731a92109f9c8a29a8df4592d2ba
- Measured timeline: 76bfb5b4161cfceae13c4438face28696a90b320a04189efd491a8b2058211cb
There are 319 sentences, 68 segments and 1861.110 seconds. The old job clock
was not assumed equivalent; selection was rerun on this exact generated pair.

Owned music and existing images were downloaded from the project's public
v0.0.0-cloud-assets-20261013 release and verified against the source manifests:
- music.flac: 1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c
- bg-lamp-window.png: e751e3c917d9b154aade9ec49f25b1da564626273af0bcb9c6f5be582ca841a8
- bg-moonlit-sea.png: a08cf077c6ea6aeef018f5ca066aa75dfd138093aa5804e33691a1b57e5a9eb1
Tools: kokoro-onnx 0.4.9, ONNX Runtime 1.20.1, NumPy 2.2.6,
espeakng-loader 0.2.4, soundfile 0.13.1, OpenCV headless 4.10.0.84;
local CPU only, no external generation job or paid API.

## Candidate and qualification limits
candidate-selection.json is MEASURED_ONLY, not model-rated. Every proposed
window was independently accepted by the producer on source-timeline.json.
The rendered candidate uses 969.668–1001.937, plus the existing 0.5-second tail.
Its complete opening is “I can tell the truth about this day.” (2.795 seconds).
It resolves with “I entrust this evening to the Lord, carrying gratitude and
honest need into the same prayer.” No narration or timing was changed to pass.

The native MP4, exact technical measurements and inspected frames are identified
in sample-measurements.json. Technical QA and frame inspection do not replace
listening or the designated watched review. An audio inspection attempt returned
“audio content omitted because you do not support audio input”; no listening is
claimed. The required gemini-3.8-flash review remains BLOCKED because it needs
credential-backed access or workflow execution outside current authority.
No alternate reviewer, invented score, publish=true or approval is supplied.

Existing production artifacts and frozen QA remain untouched. The sample is a
candidate for review, not an approved Short. Full completion remains BLOCKED
until actual listening and the unchanged designated watched review are available.
