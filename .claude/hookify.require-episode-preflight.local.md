---
name: require-episode-preflight
enabled: true
event: bash
action: block
pattern: ^(?![\s\S]*episode_build\.py\s+verify-preflight)[\s\S]*(\bgh\s+workflow\s+run\s+['"]?(\.github/workflows/)?episode(\.yml)?['"]?(\s|$)|/workflows/episode\.yml/dispatches)
---

**Bloqueado: nenhum build de episódio sem preflight** (E106, dono 2026-10-26: "um erro nunca pode se repetir").

Rode antes, na mesma linha de comando:
`python3 -I -B migration/production/bible/episode_build.py verify-preflight <plano> && gh workflow run episode.yml -f plan=<plano>`

O relatório `migration/evidence/preflight/<episódio>.json` (PASS, ligado ao sha256 do plano e do characters.json)
sai de `episode_build.py preflight <plano> --voice <python do Kokoro> <work preparado> --refs --write` e entra por PR.
O próprio `episode.yml` roda o mesmo verify no primeiro passo.
