# Build evidence discovery: manual review

Scope: E207, the read-only discovery helper, its tests, the existing heartbeat
job and canonical PR test registration. This is not an audiovisual review or
execution of an unavailable review plugin.

- Uses only an explicit paginated GET for the fixed owner's repository.
- Subprocess arguments are an array, not shell text; execution is bounded.
- The independent heartbeat job has contents:read only, no provider secrets,
  dispatch, publishing, merge, score or approval path.
- Branch names and commit hashes are checked before rendering summary text.
- Invalid API data, API errors and timeouts fail; they do not become empty work.
- Historical branches are explicitly inventory, not automatically pending.
- The designated supervisor must fetch the report at the exact commit and
  reconcile current plan/hash/QA and existing review before taking an action.
- No extra schedule or status ledger. Logs and the existing job summary carry
  discovery. The unavailable autonomous reviewer invocation remains unresolved.

Regression: before the workflow change, the heartbeat discovery integration
test failed. Afterward all five discovery tests passed; error registry 13,
heartbeat 13, schedules 3 and dispatch guard 33 tests passed locally.
The canonical run executed 83 suites: 80 initially passed. Two failed because
OpenCV was absent locally; one static workflow-isolation test treated everything
after runner-wake as part of that job. Discovery was moved before runner-wake
without changing the existing test or credentials; both discovery and runner
tests then passed. OpenCV-dependent tests are rerun after installing the missing
local dependency. CI must pass before integration; the initial failures remain
part of this record.

Read-only live inventory on 28 October 2026: 414 branches across five API pages,
six matching historical episode-build branches (Genesis 7 and 8), no matching
long-build or Genesis 9 delivery. This does not prove absence of media elsewhere
and does not authorize rerendering historical episodes.
