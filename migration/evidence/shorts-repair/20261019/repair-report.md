# pilot-012 Shorts repair: verified checkpoint

Baseline: commit998e11b7598e31110e4f76619ab85833e23c5e0c, run39320311830.
The three baseline files passed technical QA. Watched scores were7.5 and6.8;
the third was NOT_REVIEWED_ProviderFailure. All remained publish=false.

## Root causes checked in code and records
- The selector accepted a timeline clause ending in a colon as the opening;
  it scored a later hook that was not the spoken opening. The producer correctly
  hid that overlay, leaving the weak opening unchanged.
- Neither selector nor producer enforced the existing complete-line≤3s rule.
- A period and the word “will” could score an incomplete new reflection as a
  resolution. Selection now finishes the authored segment or an explicit
  resolving statement; both ends remain on actual sentence timestamps.
- Review discarded ProviderFailure.code and diagnostic. The historical cause
  cannot be recovered: quota, outage and invalid request are not established.
  The repair preserves bounded categorical HTTP/provider fields, never prose,
  raw bodies, URLs or credential values. Reviewer function AST is unchanged.

## Repairs and tests
21 offline selection/producer regressions PASS;4 diagnostic tests PASS.
Tests include the three actual rejected baseline openings, exact3.000s boundary,
context/continuation rejection, actual timeline windows, original KJV/caption/
zoom constraints and a0.5s picture fade only after the last spoken word.
The hook is an honest prefix of the actual first line, never a stronger later
line. Its existing200ms fade and the continuous1.00→1.06 zoom provide restrained
motion; no CTA, figure, extra scene frequency or rubric relaxation is introduced.

candidate-selection.json is measured-only on the repository timeline, with
input hashes. These are proposed source spans, not model-reviewed winners.
The strongest measured candidate now starts “I can tell the truth about this
day.” and resolves by entrusting the evening to the Lord (about32s).

## Media provenance and current limits
The repository timeline differs slightly from the old Shorts job's regenerated
narration clock. No old timing is being applied to unverified audio.
The original source archive SHA256 was verified:
fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10.
The existing Kokoro adapter and pinned public assets are being used locally to
regenerate the unchanged pilot012 narration with its own measured timeline:
- kokoro-v1.0.fp16.onnx: f3a290d384fbb27966d462905c71a46cef9e5fd00516b40df32a0b4afe77ac96
- voices-v1.0.bin: bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d
Owned music and existing lamp/window and moonlit-sea images were downloaded from
the project's public release and byte/hash verified against their manifests.
Actual source-text selection will be revalidated against the regenerated clock
before the native sample is rendered. No timing or text is changed to force PASS.

Watched review remains NOT_RUN. No approval/publication is claimed. The only
permitted reviewer remains gemini-3.8-flash, item≥7 and overall≥8; no secret,
workflow dispatch or paid service was used. Existing production artifacts and
frozen QA files are untouched.
