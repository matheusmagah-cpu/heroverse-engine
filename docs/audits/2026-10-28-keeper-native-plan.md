# Keeper native allocation (E209)

Base: `11cf649d257fbd97b43f865dfdf7949d1c57c73f`.

The latest owner direction requires native Pavo speech for the Keeper. The draft
still contained thirteen explicit Kokoro overrides among fourteen Keeper blocks;
four blocks were assigned to still motion, including two borrowed stills. The
new regression failed in all fourteen subcases before the plan correction
(thirteen wrong routes, one absent native-wait contingency).

The plan now uses its existing native route for every Keeper block, lists each
under talking video, removes those two still aliases, and explicitly waits for
matching approved native clips rather than substituting a different voice or a
still. No native generation, claim, provider call or dispatch was made.

This is a draft allocation correction, not generated footage or voice approval.
The canonical Keeper reference in voices.json is unchanged. The nine God blocks
remain Kokoro with no human figure. Narration, title, all non-Keeper shots,
character references, media, prior approvals and frozen QA are unchanged. Those
approvals remain historical evidence; changed requests need new valid evidence.
The source planner and verifier still enforce their existing hash and speech
checks. A new measured preflight must replace the stale report before production.

Scope is the Keeper in arc-01 only. Non-Keeper route choices, Short-native support,
material shortages and the final reviewer's identity/access remain separate open
items. Native quota is unknown; no cost or quota allowance is inferred from this
plan. Existing provider-block handling remains untouched.

Manual diff/security review: no secrets, network logic, scheduler, dependencies,
reviewer identity or gate changes. No historical approval was rewritten. The
regression checks every Keeper block and all nine God blocks; the existing strict
draft-plan test also passes. Remote CI must pass before integration.

Validation: 14 clean failing subcases before the plan correction; DraftArc1 2/2,
long-plan 51/51, sources 38/38, register 13/13 after it. The complete canonical
83-suite list passed in the existing validation venv in 66.17 seconds. A structured
comparison against the base confirmed that all non-Keeper shots and narration,
title and other unaffected plan fields are identical. `git diff --check` passed.
