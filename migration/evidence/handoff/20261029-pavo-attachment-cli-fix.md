# Pavo transfer CLI correction — 2026-10-29

PR537 merged as e5cb8cc63c2d4e9f31821c435a753e14d89e69ab; both CI runs passed.
Dispatcher 40833566975 acknowledged the one request on main 7459ffce.
Pavo run 40833596089 / attachments job 123313291421 failed on the claim command,
before any claim or provider call: isolated Python could not import client.
Generation/upload steps were skipped. There is no uncertain provider POST here.

E217 records root cause and correction. The subprocess regression of the exact
-I -B CLI failed before the fix, passed after. Only the resolved local adapter
directory is added to sys.path. Frozen criteria, source state and claims are
unchanged. No new request is added. After this correction passes CI and merges,
rerun the failed job of 40833596089 once; checkout main receives the corrected
CLI. If any claim exists at that time, reconcile it rather than overriding it.
Manual review: local import path only; no new network, credential, upload or
approval permission. Unavailable review plugins were not claimed.

Validation: 85/85 canonical local suites passed with installed runtime OpenCV
available in the isolated validation venv. 12 attachment tests passed.
git diff --check passed. Remote CI and merge are still required.
