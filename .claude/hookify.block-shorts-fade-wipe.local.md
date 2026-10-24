---
name: block-shorts-fade-wipe
enabled: true
event: all
action: block
tool_matcher: mcp__vidIQ__vidiq_compose
conditions:
  - field: format
    operator: equals
    pattern: vertical
  - field: scenes
    operator: regex_match
    pattern: ["']kind["']\s*:\s*["'](fade|wipe)["']
---

**Bloqueado: Shorts usam só "cut" entre cenas** (regra do dono, PROMPT_GUIDE.md).

No `vidiq_compose`, `fade` e `wipe` fazem a cena seguinte começar do preto. Troque o `transitionIn.kind`
para `cut`; `dip_to_black` só onde for intencional (ex.: virada para a oração final).
