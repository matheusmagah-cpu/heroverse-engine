---
name: block-approval-json-by-shell
enabled: true
event: bash
action: block
pattern: (>>?|\btee\b[^|;&\n]*|\bsed\s+-i[^|;&\n]*|\b(mv|truncate)\b[^|;&\n]*|\bgit\s+(checkout|restore)\b[^|;&\n]*|\bopen\([^)]*)\s*['"]?[^\s'"|;&]*APPROVAL\.json|\b(cp|install)\b[^|;&\n]*\s['"]?[^\s'"|;&]*APPROVAL\.json['"]?\s*($|[|;&\n])
---

**Bloqueado: APPROVAL.json nunca é escrito à mão**, nem pelo shell (regra do dono).

Ler (`cat`, `jq`, `git show`) e copiar para fora (`cp ... /tmp/x`) é permitido. A aprovação sai só do `approve.yml` → `prepublish_gate.py`.
