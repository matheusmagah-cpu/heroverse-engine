# SPEC v5 capability proof: BLOCKED, not qualified

Date: 2026-10-20 UTC. Issue #183, existing PR #185.

## Real partial output

`images/bg-shepherd-lamp-gate.png` is an original native output from the built-in OpenAI image generation tool, not a prompt placeholder. Model identifier: null (not exposed by the tool). One generation completed between approximately 14:19:21 and 14:20:09 UTC; exact generation time: null (no tool timing receipt). No reference images were supplied. No upscale, crop, resize or editing was applied. No paid API, upgrade or purchased credits were used.

Exact scene plus style:

An empty pasture gate beside a visible warm oil lamp, a gentle path and silver night sky beyond, no people, no text, photorealistic cinematic 3D render, volumetric light rays, global illumination, shallow depth of field, rich depth and atmosphere, ultra-detailed, no people, no text

Additional output-format instruction supplied to the tool:

Output format constraint: native 16:9 landscape at 2048×1152 pixels or larger, no upscaling. One image, no border, no lettering.

Measured original file: 2,786,331 bytes, RGB PNG, 1672×941. SHA256: `17357e0794b2afd829de324ddcd7948858666e982ec392a2676642619161b13e`.

`ffprobe -v error -show_entries stream=codec_name,width,height -of json images/bg-shepherd-lamp-gate.png` returned `codec_name=png, width=1672, height=941`.

- Native resolution ≥1920×1080: **FAIL**.
- Exact 16:9: **FAIL**, 1672×9 = 15048, 941×16 = 15056.
- PNG ≤4 MB: PASS.
- Direct visual inspection: visible warm lantern at upper-left, open gate foreground, moon upper-right, deep landscape layers. No visible people, text or logos. Right gate attachment and distant buildings have stylized fine details; these are visual observations, not a comprehensive artefact-free certification. The landscape looks photorealistic/synthetic; realistic=true for disclosure consideration, but no publication is authorized by this sample.
- Other three images: absent, generation not repeated after the measured specification failure.
- Both animation MP4s: absent. Video ffprobe results: null (no files).

## Capability and terms

The built-in tool schema exposes prompt, transparency and image-reference controls, but no documented numeric width/height parameter. Asking for 2048×1152 did not establish that capability. No identical retry or API/model switch was made.

Read-only check of the configured Runway workspace at 14:19 UTC returned authenticated=true, Free plan, availableVideoModels=[]. No video job, trial, upgrade, payment, credential or permission change was requested. This is a limitation of that configured service, not proof that all local animation methods are impossible. No static pan/zoom has been mislabeled as natural scene animation.

Images/day and clips/day: null. No daily capacity test or published applicable quota was available; one image attempt is not a throughput guarantee.

Commercial rights reference, accessed 2026-10-20: https://openai.com/policies/terms-of-use/ . The terms assign output ownership as between the user and OpenAI to the extent permitted by law, subject to the terms and applicable policies. This is not a public-domain licence or a guarantee of exclusivity, third-party clearance, copyright eligibility or YouTube monetization. No new agreement was accepted during this task. Final YouTube rights/policy review remains pending.

## Scope history (resolved by SPEC v5)

The existing branch/PR185 contains `migration/evidence/dot-capability/20261019/report.md` from its earlier claim. SPECv4 permits only `migration/evidence/dot-capability/20261020/**`. The legacy file was not edited or deleted. It remains outside the current allowed diff; scope cannot be represented as PASS. Main was merged without rebase or force-push.

Historical question was superseded by SPECv5 for scope. Native image and real animation capability remain unresolved; no requirement was reduced.

## Execution audit and uncertain remote effect

- 14:18 UTC: #232 was accepted by Claude at f5dac2f and merged as ff056cc7. Existing RESULT was reconciled to DONE; no merge or market-panel dispatch was duplicated.
- 14:19 UTC: existing #183/PR185 resumed, CLAIMED comment https://github.com/matheusmagah-cpu/heroverse-engine/issues/183#issuecomment-6293036175 . Existing branch was fetched and main ff056cc7 merged locally without rebase. Local merge commit 4cacec95f3064b4cba49c1292d7910482b554887; not pushed.
- 14:19 UTC: read-only configured Runway capability lookup returned Free and no video models. No generation or account change there.
- 14:19–14:20 UTC: one built-in image-generation call with the exact scene/style and explicit output-size constraint above. Observed output failed native dimensions. No repeated generation, upscale, crop or conversion.
- 14:20 UTC: `file`, `stat -c %s`, `sha256sum` and `ffprobe` measured the actual PNG. `file`: PNG, 1672 x 941, 8-bit/color RGB, non-interlaced. `stat`: 2786331. Image SHA and ffprobe output are above. Original and evidence copy retained.
- 14:20–14:22 UTC: read current OpenAI terms reference and documented the actual output, unresolved model/quota, missing videos and legacy-path conflict. This is a factual report, not approval.
- 14:22 UTC: post-merge market-panel run39437927428 was observed SUCCESS, including collection, model/scoring, daily intelligence and evidence commit. Commit f11679789626ae0fecbfe0204b5491af16e018c0. Later read of its panel: captured14:18:04UTC,1223channels,2399units,unavailable_channels=[]. This verifies operational completion, not that a live404 happened during that run.
- About14:23–14:24 UTC: image bytes were read locally in base64 chunks and passed once to GitHub create_blob to preserve the failed sample, encoding=base64. No branch/ref update was attempted. The operation prompted confirmation and remained pending; no approval was assumed.
- 15:56:41 UTC: waiting call finished with `TypeError: Cannot read properties of undefined (reading 'sha')` in the wrapper after create_blob. Raw tool response had not been saved before dereferencing structuredContent.sha. It is unavailable; denial, cancellation or provider failure cannot be distinguished. The error does not establish success or permission.
- 15:56–15:57 UTC: `git hash-object images/bg-shepherd-lamp-gate.png` returned c5c36c8486306f0006a1347a8c002ca56d07af4b. Read-only GitHub GET `/repos/matheusmagah-cpu/heroverse-engine/git/blobs/c5c36c8486306f0006a1347a8c002ca56d07af4b` returned404 NOT_FOUND. No persistence is confirmed. No retry or alternate upload route was used.
- 15:57 UTC: issue183 body remains SPECv4; no new instruction in PR185. Remote PR185 remains at3a7c3709e286883f5c0b4082cf5bc93262bec767. Its old CI39280009136 was successful but predates this work and does not qualify these files or SPECv4. New-delivery CI=null, because no new commit/ref has been delivered.
- 15:58 UTC: temporary direction instructed preservation as FAIL/BLOCKED, no new generation or upload retry, and requested this detailed audit. Pending technical decisions remain separate from execution.

Current paths:
- Local new allowed: `migration/evidence/dot-capability/20261020/report.md` and `migration/evidence/dot-capability/20261020/images/bg-shepherd-lamp-gate.png`.
- Remote existing legacy diff: `migration/evidence/dot-capability/20261019/report.md`, untouched; outside SPECv4 allowed glob.
- All four qualified images, both qualified MP4s, new remote commit, new-delivery CI, and daily capacity proof remain absent/unproven. RESULT remains BLOCKED, never DONE.

## SPEC v5 reconciliation at 16:01 UTC

Read the remote consolidated issue body after its confirmed 16:00:57UTC update. Exact allowed paths now cover these reports, all requested images/videos and the historical report. `20261019/report.md` must remain byte-identical to Git blob915800bec4a3b5d4bc765b07f450bc38a67d6885. This corrects path matching, not media acceptance. Prior statements about an out-of-scope legacy file describe v4 only and are no longer current rules.

Direction permits separate preservation of textual audit evidence, but not retrying the uncertain PNG upload. The upcoming text-only commit deliberately omits the PNG; it does not use a different route to upload those bytes. All image/video acceptance failures remain. Remaining question: which documented permitted native image generation route can meet ≥1920×1080 at zero added cost? Evaluate real internal-scene motion only after a qualifying source exists; no model/provider switch or new generation was made.
