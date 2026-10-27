---
name: block-cf-images-bad-pilot-mcp
enabled: true
event: all
action: block
tool_matcher: mcp__github__actions_run_trigger
conditions:
  - field: workflow_id
    operator: regex_match
    pattern: ^(\.github/workflows/)?cf-images\.ya?ml$
  - field: inputs
    operator: regex_match
    pattern: ['"]pilot['"]\s*:\s*['"](?!(pilot-[0-9]{3}|characters)['"])
---

**Bloqueado: o `pilot` do cf-images é só `pilot-NNN` ou `characters`** (E96, E106).

Sem o prefixo `migration/production/`: o passo de entrada recusa qualquer outra forma (PILOT_INVALID).
