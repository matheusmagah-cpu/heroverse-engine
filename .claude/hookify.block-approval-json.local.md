---
name: block-approval-json-by-hand
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: (^|/)APPROVAL\.json$
---

**Bloqueado: APPROVAL.json nunca é escrito à mão** (regra do dono).

A aprovação é emitida só pelo `approve.yml` → `prepublish_gate.py`, ligada ao hash do arquivo.
Para aprovar um vídeo, corrija a causa e deixe o gate rodar; a revisão Claude vai em
`inspection/claude_review.json` / `inspection/preview_review.json` (ops/CLAUDE_REVIEW.md).
