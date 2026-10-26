---
name: require-episode-preflight
enabled: true
event: bash
action: block
pattern: ^(?!\s*python3(?:\s+-[IB]+)*\s+(?:\./)?migration/production/bible/episode_build\.py\s+verify-preflight\s+(['"]?)([^\s'";&|]+)\1\s*&&\s*gh\s+workflow\s+run\s+['"]?(?:\.github/workflows/)?episode(?:\.yml)?['"]?(?:\s+--ref\s+['"]?main['"]?)?\s+-f\s+(['"]?)plan=\2\3(?:\s+-f\s+['"]?resume_run=[0-9]*['"]?(?:\s+-f\s+['"]?regenerate=[a-z0-9][a-z0-9,-]*['"]?)?)?\s*$)[\s\S]*(\bgh\s+workflow\s+run\s+['"]?(\.github/workflows/)?episode(\.yml)?['"]?(\s|$)|/workflows/episode\.yml/dispatches)
---

**Bloqueado: nenhum build de episódio sem preflight do MESMO plano** (E106, dono 2026-10-26: "um erro nunca pode se repetir").

Só esta forma passa, sozinha na linha de comando, com o mesmo caminho de plano nos dois lados do `&&`:
`python3 -I -B migration/production/bible/episode_build.py verify-preflight <plano> && gh workflow run episode.yml [--ref main] -f plan=<plano> [-f resume_run=<id> [-f regenerate=<ids>]]`

`regenerate` só depois de `resume_run` (dono 2026-10-26: refazer só as cenas reprovadas; o `episode.yml` recusa
REGENERATE_REFUSED/UNKNOWN_SHOT/WITHOUT_RESUME). `;`, `||`, um segundo comando ou outro plano são bloqueados; a API (`.../episode.yml/dispatches`) e o conector também.
O gate real é o próprio `episode.yml`, que roda o mesmo `verify-preflight` no primeiro passo: este hook só evita
uma execução que já nasceria recusada. O relatório `migration/evidence/preflight/<episódio>.json` (PASS, ligado ao
plano, aos personagens e imagens que ele usa, às sondas e ao código) sai de
`episode_build.py preflight <plano> --voice <python do Kokoro> <work preparado> --refs --write` e entra por PR.
