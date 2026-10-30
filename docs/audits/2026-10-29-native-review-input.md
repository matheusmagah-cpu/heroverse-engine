# E220 — browser dispatch certificate transport

Manual code/security review by Codex, not a claim that unavailable Claude plugins ran.
GitHub renders string dispatch inputs as single-line INPUT elements. The actual
DOM was inspected before dispatch; flattening the certificate reproduced an
OpenSSL failure locally. No provider request was made. The fix validates the
public CERTIFICATE envelope, size and base64 before canonical line wrapping.
Other PEM types, including private keys, are refused. Encryption and the exact
media/reviewer/Free Tier bindings are unchanged. The regression performs a real
CMS encrypt/decrypt roundtrip from the browser's flattened input shape and proves
that plaintext private receipt data is absent from the artifact. Existing gates
and all unrelated source/renderer files are unchanged.
