# RapidAPI MCP: conexão do executor verificada

O executor GitHub Actions do HeroVerse usa o endpoint `https://mcp.rapidapi.com`,
roteamento fixo `x-api-host: youtube-info-download-api.p.rapidapi.com` e o secret
cifrado `HERO_RAPIDAPI_KEY` em `x-api-key`. A chave existente foi vinculada após
confirmação explícita do titular; não é necessário repetir login ou autorização.

## Resultado vigente

Execução [38737240760](https://github.com/matheusmagah-cpu/heroverse-engine/actions/runs/38737240760),
commit `cea11b766494ae1a015d7589f545e8c7e166fdca`: **Success**, 13s no total,
6s no job. Os 14 testes offline e a prova real passaram. Revisão negociada:
**2024-11-05**. Catálogo real com nove ferramentas: progress, playlistSize,
channel, playlist, info, download, search, charts e subtitles. Sem próxima página.

O servidor responde à notificação sem id `notifications/initialized` com HTTP200
e erro RPC **-32601**. O cliente registra esse método indisponível e continua
somente ao catálogo em modo de compatibilidade declarado. Não afirma confirmação
padrão da notificação ou conformidade estrita do servidor. Outros erros continuam
fatais. Histórico das três falhas anteriores preservado; não repetir seus clientes.

## Limites desta prova

Workflow apenas manual, contents:read, teto de dois minutos, Python padrão,
sem SDK/servidor novo. Apenas initialize, notifications/initialized e tools/list;
**tools/call é recusado antes da rede**. Não há retry, redirect, cron ou upload
de artefatos. Respostas limitadas a 1MiB; recibos omitem chave, headers privados,
sessões e mensagens arbitrárias do fornecedor.

A conexão pertence ao executor do repositório. O plugin pessoal do ChatGPT
continua sem ferramentas disponíveis neste chat. Esta prova verifica transporte
e catálogo, não a autorização para executar download, vídeo, áudio, qualidade
ou capacidade gratuita recorrente.

Recibo: `migration/evidence/cloud-video-player-20261015/rapidapi-cloud-mcp-live-result.json`.
Próxima etapa única: teste nativo já registrado
`20261015-rapidapi-native-j2rk8ycXe3c-0-40-v1`, ainda não enviado. Conferir franquia
e banda com limite de gasto zero, preservar job antes de retomadas e medir bytes,
imagem e áudio recebidos. Não repetir conexão aprovada, QA do master ou assinatura.
Produção, publicação e supervisor permanecem OFF.

Teste offline:

```sh
python3 -m unittest discover -s migration/diagnostics/rapidapi-mcp -p test_connection_probe.py -v
```
