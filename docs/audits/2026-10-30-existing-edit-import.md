# Verified security sweep: existing-edit-import, 2026-10-30

## Context

Scope: new `migration/production/bible/existing_edit.py`, the import/render CLI
entry points and reconstruction guards in `migration/production/bible/episode_build.py`,
and `ExistingEditImport` in `migration/production/bible/test_episode_build.py`.
The direct consumer `migration/production/draft_render.py` entered verification
when the implementing agent corrected F1 at that boundary. No workflow, secret or
publication code changed. Trigger: explicitly requested additional review of
confinement, hashes, idempotency and semantics before using the local importer.

Original procedure: Verified Security Sweep **1.4.0**, upstream
`SecPlusDev/verified-security-sweep`, commit
`90a73a192b404ad139bee970f49f73f07410c949`; original skill, references and scripts
previously installed with verified hashes. Actual reviewers: **Codex**.
This is code review and synthetic local verification, never voice, perceptual
quality, source-rights or publication approval.

Branch: `claude/import-existing-audio-20261030`. Local HEAD
`05bf313ae88255271a6ea6d6c6dc2f344cc9c0c9` reconstructs the supplied upstream main
snapshot identified by prefix `34a3ead`; it does not contain the uncommitted new
importer. The pre-fix importer hash captured during this run was
`8f91fb63388816115d5eb5325b77b4cd3e9f98378eb6559614ecf85e7b9309f7`.
No immutable Git commit of the vulnerable working files exists. Implementation
continued during review; the final hashes below bind the final source inspection
and focused tests. No historical commit was invented or reconstructed.

| Final working file | SHA256 |
|---|---|
| `migration/production/bible/existing_edit.py` | `e17f089ddb7e710b63048aba1cb7bb9f2a271956142c1666a9b525b490d51a26` |
| `migration/production/bible/episode_build.py` | `39c110347b8db8a9ed29b5302153ace12069024d65d6e995f6e0de66b1dee1d9` |
| `migration/production/bible/test_episode_build.py` | `39f5fa9656c4ace47be40cadaf8a5f52d19d9c4c3a27eb87f0b126a4ce1c29ac` |
| `migration/production/draft_render.py` | `30f71e113ab099a3bd592e3b6bd25420a76a5d8d44ba6e7d09835c7daa8d1da8` |

Current AGENTS, CLAUDE, security guidance, categories and registry were read.
All 33 prior dated audits and the undated Pavo preparation report matched the
previously read files byte-for-byte; their pre-read was retained. No `docs/specs/`
or coverage matrix exists. Relevant closures: `2026-10-28-preflight-resume.md`
(E211: synthesis replay, checkpoints, input binding, symlinks),
`2026-10-29-draft-render.md` (E219: sealed rendering inputs, exact frame/audio
validation, cache and atomic outputs), `2026-10-26-refusal-parity-e106.md`
(episode/path containment and stale bindings), and
`2026-10-28-gpt-reviewer-handoff.md` (honest identity and publication boundaries).
F1 is a new importer-to-renderer boundary, not a re-report of E219's fixed
within-render snapshots.

Original `fresh_code.py` reported episode_build among recent high-churn modules
with test mentions. It cannot see the uncommitted new importer as shipped history.
Original `findings.py recheck` found no open indexed findings; no recorded commands
ran. Initial `sweep_status.py --check` passed with 18 zones and 33 dated reports.
Probes derived from project rules covered path traversal/symlinks, descriptor
sealing, expected hashes, subprocess argument lists, restart state, approval flags
and CLI guards; a grep hit was not treated as a finding.

## Delegation

One fresh read-only Codex reviewer, `existing_edit_reader`, read the original
skill and verification reference, current project rules, all prior audits,
categories and registry, then the bounded implementation and direct consumers.
The brief required exact sink lines, source-to-sink/missing-mitigation evidence,
calibrated severity, explicit refusals and coverage; it prohibited network,
production actions, edits and Git mutations. It explicitly named the historical
closures above and required a current bypass before reopening them.

The coordinator independently found and verified F1, reopened the reader's cited
lines, and ran the real synthetic FFmpeg interleaving test. Reproduction and this
report stayed with the coordinator. The implementing root agent alone changed
production code. The reader then independently checked the fix and final pending
marker/AAC/offset deltas; it did not supply a generic substitute for the skill.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| F1 imported captions/manifest may change between verification and consumption | existing-edit-import | VERIFIED REAL | Medium | Medium, fixed before final verification | Local concurrent writer and a narrow interval; DRAFT only, no publication bypass. | Initial real caption-interleaving test ran, fails as expected; legitimate render passes. Final fix at `migration/production/bible/existing_edit.py:247`, `migration/production/draft_render.py:319`, `migration/production/draft_render.py:367`. Final reproduction tests ran, pass. |
| F2 NaN segment duration passes the exact-frame comparison | existing-edit-import | VERIFIED REAL | Low | Low, fixed before final verification | Import-format correctness only; downstream renderer already refused nonfinite seconds. No playable or publishable approval bypass. | Initial isolated function probe ran and observed `IMPORTED_NOT_APPROVED` with NaN. Final explicit finite guard `migration/production/bible/existing_edit.py:156`; `docs/audits/reproductions/test_existing_edit_bound_render.py:99` ran, passes. |
| R1 relative path or symlink escapes the imported package | existing-edit-import | FALSE POSITIVE | High candidate | - | Existing mitigation: strict components, directory descriptors, no-follow, regular file, expected hash and sealed bytes. | `migration/production/bible/existing_edit.py:32`, `migration/production/bible/existing_edit.py:47`, `migration/production/bible/existing_edit.py:50`, `migration/production/bible/existing_edit.py:54`; path/hash/symlink regressions ran, pass. |
| R2 resume silently replaces an earlier import with changed source bytes | existing-edit-import | FALSE POSITIVE | Medium candidate | - | Resume verifies delivered outputs and the binding, not mutable originals that are no longer consumed. | `migration/production/bible/existing_edit.py:104`, `migration/production/bible/existing_edit.py:105`; idempotent resume and changed/partial-output regressions ran, pass. |
| R3 final imported workspace is eligible for voice reconstruction | existing-edit-import | FALSE POSITIVE | Medium candidate | - | Final receipt or pending marker blocks CLI and direct lines entry; E211 rejects unrelated nonempty work. Interrupted-import hardening was integrated by the root agent during review. | `migration/production/bible/existing_edit.py:27`, `migration/production/bible/episode_build.py:2195`, `migration/production/bible/test_episode_build.py:2394`; completed and interrupted guards ran, pass. |
| R4 metadata grants voice authenticity, quality or publishing approval | existing-edit-import | FALSE POSITIVE | High candidate | - | The owner can edit local metadata; the importer does not authenticate that owner or issue quality approval. | `migration/production/bible/existing_edit.py:215`, `migration/production/draft_render.py:454`; DRAFT flags and real-copy tests ran, pass. |
| R5 sealed HLS playlist reads an unbound external local media file | existing-edit-import | FALSE POSITIVE | Medium candidate | - | Refused for the concrete fixture only; no blanket assertion about every demuxer. | Both reviewers' synthetic HLS probes ran: installed ffprobe rejected the sealed descriptor's nonstandard extension/MIME. The coordinator independently reproduced that refusal using `migration/production/draft_render.py:141`. |
| R6 slicing fabricates sentence/phoneme boundaries or retimes PCM | existing-edit-import | FALSE POSITIVE | Medium candidate | - | Frame intervals are operator-supplied group boundaries; voice identity and factual correspondence still need review. | `migration/production/bible/existing_edit.py:196`, `migration/production/bible/existing_edit.py:200`, `migration/production/bible/existing_edit.py:204`; nonzero offset PCM and no-retime regressions ran, pass. |

## Confirmed defects

**One Medium defect confirmed and fixed; zero open Medium-or-higher defects at
final verification.** The separate Low item F2 is recorded below, not included in
that headline count. No Critical or High defect was established.

### F1: imported hash verification ended before the renderer consumed the files

The original sink was the unqualified `dr.render(work / 'manifest.json', output)`
call, initially at line 226 of the new importer. `verify()` checked outputs using
sealed snapshots, then closed them. The next renderer call reopened the manifest
and captions; the renderer independently sealed its own bytes, but captions had
no expected hash from the importer receipt. A local process changing captions
between those phases could produce a successful DRAFT from different bytes.

The initial test used a real 60-frame synthetic render and AAC mix. The legitimate
case passed. The controlled caption change made
`test_caption_change_after_verify_never_becomes_imported_render` fail because
rendered subtitle SHA256
`ff09344e420f4aa49e6222e5633c9456ab6a015b33363f2a8ff462f5fd7c30a1`
differed from the imported receipt's
`3881fe83d17e38e8c782043525a6660466288dbf275d2a1abf1388234a5b9f8f`.
This was a runtime observation, not only a race inferred from source reading.

The root agent propagated the receipt's expected manifest/subtitle hashes into
the existing renderer. The manifest hash is checked on the exact raw bytes before
JSON parsing; the expected subtitle hash is applied while building the sealed
snapshot actually consumed by FFmpeg. The final interleavings for both caption
and manifest changes pass, and the intact path still renders 60 frames with
identical audio packets and false publication approval. Relevant test assertions:
`docs/audits/reproductions/test_existing_edit_bound_render.py:69`,
`docs/audits/reproductions/test_existing_edit_bound_render.py:79`, and
`docs/audits/reproductions/test_existing_edit_bound_render.py:88`.

### Low: F2 nonfinite duration was accepted by the importer

The original comparison used `abs(seconds * 30 - frame_count) > tolerance`.
NaN makes that comparison false. A hash-bound synthetic manifest containing NaN
therefore received `IMPORTED_NOT_APPROVED` and wrote NaN into its delivered
manifest. The downstream renderer already rejected nonfinite seconds, so the
impact was accepting an unusable import, not a failed media check becoming PASS.
The initial proof was an executed isolated function probe, not a retained failing
unittest. The subsequently written regression requires refusal before destination
creation. It passes with the explicit finite-number check and the ordinary
finite-duration path still passes.

### Findings-index evidence limitation

The vulnerable source was an evolving, uncommitted working tree. Its captured hash
and real F1 failure are recorded above, but its bytes were not preserved as an
immutable Git snapshot. Local HEAD is older reconstruction history and must not
be assigned to these findings. The final code's lines must not be mislabeled as
the original vulnerable snapshot either.

Consequently no fabricated commit/snippet entry was appended to `findings.jsonl`.
The empty index can pass `findings.py check`, but that does **not** validate F1/F2
or satisfy the original skill's commit-bound finding-index step. This is an explicit
recording gap: the original method's delegated reading, verification, reproduction
and final regression work ran, while full historical index compliance is not
claimed. The final PR can bind the corrected code hashes and retained regressions;
it cannot retroactively manufacture the missing vulnerable commit.

## Refused or unconfirmed candidates

- R1: refused, existing mitigation. Package data paths cannot be absolute, dotted
  traversal or symlink components; payloads are hashed and sealed before writing.
  This is not provenance authentication for the root directory chosen by its owner.
- R2: refused, claim correctness. An existing successful import is verified from
  its delivered files and unchanged binding. A changed destination fails; an
  interrupted destination is preserved and refused, never silently overwritten.
- R3: refused for the final code, existing mitigation. Both completed and partial
  imports have a receipt or pending marker recognized before the generated-voice path.
  The pending marker and directory are synced before payload writes; the receipt
  is synced before the pending marker is removed. The added interruption regression
  is part of the root agent's normal correction, not a production edit by this sweep.
- R4: refused, claim correctness. Imported facts and frame mapping do not prove
  speaker identity, heard words, licensing or quality. Production/publication
  flags stay false and the consumer applies the visible DRAFT overlay.
- R5: refused, exploitability for the tested HLS path. The actual installed
  demuxer rejects that sealed playlist before rendering; synthetic external media
  was used, never private files. Other demuxers were not certified.
- R6: refused, claim correctness. PCM is sliced by declared frame indices without
  retiming; word boundaries remain null. Validating mapping/bytes does not attest
  that the claimed speech was actually heard.

## Coverage

All scoped new code, changed CLI/guards and importer tests were read. The direct
renderer was read, then its changed expected-hash boundary verified. Supporting
reads covered `sequence`, `voice_script`, `check_plan` and the E211 preflight
workspace checks. No scoped file was skipped. Other providers, workflows,
publication internals, live private packages and perceptual audio were excluded.
All three lenses were applied: exploitability, claim correctness, existing mitigation.

Final focused execution, bytecode writing disabled:

- `python3 -I -B migration/production/bible/test_episode_build.py ExistingEditImport -v`: eight tests PASS in 6.787 s; fresh reader independently ran the same eight tests, PASS.
- `python3 -I -B docs/audits/reproductions/test_existing_edit_bound_render.py -v`: four tests PASS in 2.878 s.
- `python3 -I -B migration/production/test_draft_render.py`: ten tests PASS on the unchanged final renderer hash.
- Original `check_citations.py`: 23 citations resolve to the inspected code lines, zero problems.
- Original `check_report.py`: eight verification rows, two VERIFIED REAL, six refused entries, zero problems.
- Original `findings.py check`: zero entries, zero structural problems; this does not close the historical findings-index gap described above.
- Original `sweep_status.py --check`: 19 zones, 34 dated reports, zero divergent or stale entries.
- `git diff --check`: PASS for the audit and reproduction paths.

The root agent's additional shared-narration, AAC-only mix and interrupted-import
corrections were read and covered by the final importer tests. Their findings
are not reattributed to this sweep or counted again. The full canonical PR suite
and remote CI belong to the integrating agent; they are not inferred from these
focused results.

## Hand-off

No open code fix is proposed on the final reviewed hashes. Retain the F1 regression
and final importer guards in canonical PR checks, keep the explicit DRAFT contract,
and integrate only through the normal root-owned change process. The independent
reproduction test remains under `docs/audits/reproductions/` for replay.

Record this as a bounded original-method sweep with the historical findings-index
limitation above, not complete commit-bound index evidence or whole-project
certification. This sweep wrote only the report, registry and reproduction test;
it performed no production edit, remote mutation, provider call, provider generation,
private-media review or publication. The earlier native-review sweep is separate.
