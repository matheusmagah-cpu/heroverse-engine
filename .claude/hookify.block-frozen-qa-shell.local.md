---
name: block-frozen-qa-criteria-by-shell
enabled: true
event: bash
action: block
pattern: (>>?|\btee\b[^|;&\n]*|\bsed\s+-i[^|;&\n]*|\b(mv|truncate|rm)\b[^|;&\n]*|\bgit\s+(checkout|restore)\b[^|;&\n]*|\bopen\([^)]*)\s*['"]?[^\s'"|;&]*(qa_criteria_(story_)?v[0-9]+\.json|pilot-[0-9]{3}/qa_criteria\.json)|\b(cp|install)\b[^|;&\n]*\s['"]?[^\s'"|;&]*(qa_criteria_(story_)?v[0-9]+\.json|pilot-[0-9]{3}/qa_criteria\.json)['"]?\s*($|[|;&\n])
---

**Bloqueado: os critérios de QA congelados (v2/v3/v4) nunca são alterados**, nem pelo shell (regra do dono).

Ler e copiar para um piloto novo (`cp migration/production/pilot-008/qa_criteria.json migration/production/pilot-NNN/`) é permitido.
