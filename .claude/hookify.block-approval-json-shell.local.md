---
name: block-approval-json-by-shell
enabled: true
event: bash
action: block
pattern: (>>?|\btee\b[^|;&]*|\bsed\s+-i[^|;&]*|\b(cp|mv|install|truncate)\b[^|;&]*|\bopen\([^)]*)\s*['"]?[^\s'"|;&]*APPROVAL\.json
---

**Bloqueado: APPROVAL.json nunca é escrito à mão**, nem pelo shell (regra do dono).

Ler (`cat`, `jq`, `git show`) é permitido. A aprovação sai só do `approve.yml` → `prepublish_gate.py`.
