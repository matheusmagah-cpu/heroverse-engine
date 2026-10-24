---
name: block-frozen-qa-criteria-by-shell
enabled: true
event: bash
action: block
pattern: (>>?|\btee\b[^|;&]*|\bsed\s+-i[^|;&]*|\b(mv|truncate|rm)\b[^|;&]*|\bopen\([^)]*)\s*['"]?[^\s'"|;&]*(qa_criteria_v[0-9]+\.json|pilot-[0-9]{3}/qa_criteria\.json)
---

**Bloqueado: os critérios de QA congelados (v2/v3/v4) nunca são alterados**, nem pelo shell (regra do dono).

Ler e copiar para um piloto novo (`cp migration/production/pilot-008/qa_criteria.json migration/production/pilot-NNN/`) é permitido.
