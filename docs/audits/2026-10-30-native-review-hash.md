# Native review hash readback and bounded recovery

Manual code/security review by Codex; not a plugin audit or audiovisual approval.

Run 40990049460 stopped before inference because the provider's base64 hash
decoded to hexadecimal ASCII. Strict decoding now accepts only that form or a
32-byte digest, with the same exact SHA256 comparison. No mismatch is ignored.

Recovery names the original run and reuses its provider file. GitHub must show
one completed failed attempt, successful upload start, failed file validation,
and skipped submit/poll steps. Active, possibly submitted and second recovery
operations are refused. The recovery upload phase performs no POST.

Private receipts remain encrypted; no master, private ID, URL, API key, plan
approval or score is committed. No scheduler, reviewer floor or publish gate changes.
