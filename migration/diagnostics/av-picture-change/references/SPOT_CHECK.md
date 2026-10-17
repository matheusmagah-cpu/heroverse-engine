# Spot check of the reference classification (2026-10-17): NOT ACCEPTED as a production target

Reviewer: Claude Code (AI assistant), by viewing the before/after sheets `spot-*.jpg` (blue frame = classified SCENE, orange = LOCAL). This is not a human review.

Controls q1–q5 passed in CI (run 39022595107). On real openings, the frozen acceptance rule (≥ 90% agreement with visual judgement) **fails**:

- htx4YZVYBVs (winner): 19 changes. Only 3 are real background/scene changes (title card → figure over sky, sky → river at "And I want you to hear this clearly", river → grass at "You can place it in God's hands"). The classifier labels 11 as SCENE, so about 8 of 19 are wrong (~58% agreement). The large translucent caption box (about 30% of the frame) plus the rotating SUBSCRIBE/LIKE/FOLLOW badge change more than 45% of the grid cells.
- wq9dd3z5qpk and 17uv62CEsBQ (winners) show the same failure: caption-box changes over an unchanged background are often labeled SCENE.

So the per-minute SCENE numbers in `reference-picture-changes.json` overstate scene cuts and must not be used as targets. The LOCAL counts are a lower bound on caption changes.

## Grammar of the three winners (direct visual reading of the sheets, n = 3 openings of 40 s)
1. **Title card** for the first ~1–2 s, styled like the thumbnail ("MORNING GRACE PRAYERS", "MORNING PRAYER WITH GOD").
2. **One persistent figure of Jesus** (praying hands, or hand on heart). It is a cut-out at the **left ~40%** of the frame, identical across the whole opening.
3. **Backgrounds change behind the figure** (sky, river, sunset field, forest, road, snow) every ~6–13 s: 17uv ≈ 7 backgrounds in 40 s, wq9d ≈ 4–5, htx4 ≈ 3.
4. **Large spoken-line caption in a translucent box at right-centre**, 2–5 lines, changing with every phrase (~3–4 s).
5. **Persistent channel elements**: logo or name top-left, rotating SUBSCRIBE / LIKE / FOLLOW / SHARE badge top-right, "Type AMEN" bottom-right.

pilot-002 follows this grammar. The classifier stays as an instrument for controls; a box-aware version would be needed before its rates are used as targets.
