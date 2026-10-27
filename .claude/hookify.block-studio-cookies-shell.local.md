---
name: block-studio-cookies-shell
enabled: true
event: bash
action: block
pattern: \$\{?YT_STUDIO_COOKIES|YT_STUDIO_COOKIES(?!=(\s|$))|(^|[\n;&|(]\s*)(env|printenv)\s*($|[\n;&|>)])|/proc/[^\s]*/environ
---

**Bloqueado: os cookies do Studio (`YT_STUDIO_COOKIES`) nunca passam pelo shell** (regra do dono: nunca expor segredos).

Eles dão poder total sobre a conta Google. Só o MCP `heroverse-studio` os lê, do ambiente do seu próprio processo
(`migration/integrations/studio/README.md`). Nada de `echo`/`printenv` dessa variável, `env`/`printenv` sem argumento
(listaria todos os segredos) ou `/proc/*/environ`. Para outra variável, leia-a pelo nome (`printenv PATH`).
