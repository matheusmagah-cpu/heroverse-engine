---
name: block-frozen-qa-criteria
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: migration/production/(qa_criteria_v[0-9]+\.json|pilot-[0-9]{3}/qa_criteria\.json)$
---

**Bloqueado: os critérios de QA congelados (v2/v3/v4) nunca são editados** (regra do dono).

`qa_criteria_v3.json`, `qa_criteria_v4.json` e as cópias v2 em `pilot-NNN/qa_criteria.json` têm o
SHA256 fixado em `render_queue.py`, `script_check.py` e `prepublish_gate.py`. Nunca afrouxe um gate:
corrija o vídeo, ou proponha uma nova versão (v5) congelada antes do primeiro render, com aprovação do dono.
Um piloto novo copia a v2 com `cp`, sem editar.
