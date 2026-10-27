---
name: require-episode-preflight-mcp
enabled: true
event: all
action: block
tool_matcher: mcp__github__actions_run_trigger
conditions:
  - field: workflow_id
    operator: regex_match
    pattern: ^(\.github/workflows/)?episode\.ya?ml$
---

**Bloqueado: o build de episódio não é disparado pelo conector** (E106).

Pelo conector não dá para encadear o preflight. Use o shell:
`python3 -I -B migration/production/bible/episode_build.py verify-preflight <plano> && gh workflow run episode.yml -f plan=<plano>`
