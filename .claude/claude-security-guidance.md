# HeroVerse engine security rules (read by the security-guidance plugin on every diff review)

- Credentials live only in repository secrets (`HERO_YT_AUTHORIZED_USER_JSON`, `HERO_GEMINI_API_KEY`,
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `HERO_RUNNER_PAT`). A diff that
  writes any of them, or any token, refresh token or `authorized_user` JSON, to a file, an artifact, a log line, a
  receipt under `migration/evidence/` or `migration/publish/receipts/`, or a commit message is a finding.
- Workflows: a `${{ github.event.* }}` value (issue, comment, PR title or body, branch name) or a `workflow_dispatch`
  input interpolated straight into a `run:` script is a script-injection finding; pass it through `env:` and quote it.
  A secret passed on a command line (visible in `ps` and in `set -x` output) instead of `env:` is a finding.
- `HERO_RUNNER_PAT` dispatches workflows in heroverse-runner; any new use must be limited to `workflow_dispatch` of an
  existing workflow, never contents write.
- The publish gate is the owner's quality floor: `approve.yml` → `prepublish_gate.py` writes `APPROVAL.json` bound to
  the video's `output_sha256`. A diff that writes `APPROVAL.json` outside that path, skips the hash recomputation, or
  publishes (`publish_video.py`, `publish_episode.py`) without a matching approval is a finding.
- Frozen QA criteria (`migration/production/qa_criteria_v3.json`, `qa_criteria_v4.json`, `pilot-NNN/qa_criteria.json`)
  are pinned by SHA256 in `render_queue.py`, `script_check.py` and `prepublish_gate.py`. Changing a pinned hash, or
  turning a failed or missing check into a pass (`except: pass`, a default of `True`, a skipped branch) is a finding.
- Spending: every vidIQ generation call must append to `migration/evidence/vidiq/ledger.json` and respect the daily
  ceiling in `migration/production/bible/SERIES.md`. A new paid API, billing setup or credit purchase is a finding.
- Downloads of stock footage or generated media go to a temporary or `migration/` path chosen by the code, never to a
  path built from a remote filename without containment.
