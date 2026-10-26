---
name: block-cf-images-bad-pilot
enabled: true
event: bash
action: block
pattern: \bgh\s+workflow\s+run\s+['"]?(\.github/workflows/)?cf-images(\.yml)?\b[^\n;&|]*(-f|-F|--field|--raw-field)\s*['"]?pilot=(?!(pilot-[0-9]{3}|characters)['"]?(\s|$))
---

**Bloqueado: o `pilot` do cf-images é só `pilot-NNN` ou `characters`** (E96, E106).

Sem o prefixo `migration/production/`: o passo de entrada recusa qualquer outra forma (PILOT_INVALID) e a dispensa
gasta uma execução. Ex.: `gh workflow run cf-images.yml -f pilot=characters -f engine=flux -f only=ch-noah-front`.
Antes de uma folha de referência, `episode_build.py preflight <plano>` mostra as imagens já feitas hoje contra as ~44 por dia.
