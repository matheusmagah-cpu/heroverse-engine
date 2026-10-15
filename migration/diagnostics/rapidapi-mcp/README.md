# RapidAPI MCP: qualificação da conexão

Cliente de diagnóstico para o executor GitHub Actions já usado pelo HeroVerse.
O endpoint `https://mcp.rapidapi.com` e os cabeçalhos `x-api-host` e `x-api-key`
foram observados na configuração real do fornecedor, com a conta autenticada.
O cabeçalho de roteamento fica fixo em `youtube-info-download-api.p.rapidapi.com`.

O workflow `HeroVerse RapidAPI MCP connection probe` tem apenas execução manual,
permissão de leitura do repositório e limite de dois minutos. Não executa em push,
cron ou pull request. Usa Python padrão, sem instalar SDK ou servidor intermediário.
Lê somente o segredo `HERO_RAPIDAPI_KEY` do repositório e nunca grava seu valor.

Esta etapa envia apenas `initialize`, `notifications/initialized` e `tools/list`.
O cliente recusa `tools/call`, redirects e respostas acima de 1 MiB; interrompe
erros sem repetir chamadas. O recibo sanitizado sai no log com o prefixo
`HEROVERSE_MCP_RECEIPT=`; não há upload de artefatos.

## Ponto atual

- A tela da conta RapidAPI mostra Basic Active, US$0/mês, uso agregado 0%.
  O percentual não comprova um contador exato, banda ilimitada ou reprodução.
- O GitHub mostra Free, 124 de 2000 minutos incluídos usados no mês e
  US$0 faturável de Actions. Isso cobre o teto de dois minutos desta prova;
  não qualifica toda a mineração futura.
- `HERO_RAPIDAPI_KEY` foi salvo como secret cifrado após confirmação explícita
  do titular. O valor não entra em código, logs, screenshots ou recibos.
- O pacote MCP importado no ChatGPT foi aceito como plugin pessoal, mas a
  interface oferece abertura no desktop e não expõe suas ferramentas a este chat.
  Não usar esse cadastro como prova de conexão em nuvem.

A primeira execução `38735882205` recebeu uma resposta de inicialização e parou
com `UNSUPPORTED_NEGOTIATED_PROTOCOL`; a versão exata não foi retida nesse recibo.
A correção aceita explicitamente as revisões de handshake 2025-11-25, 2025-06-18,
2025-03-26 e 2024-11-05 para os três métodos comuns. Versões desconhecidas e o
protocolo sem handshake 2026-07-28 continuam recusados. O transporte HTTP existente
é mantido; não há fallback, repetição automática ou chamada de mídia. Oito testes
locais passaram após essa mudança; falta a validação real da correção.

Não criar nova assinatura, ampliar plano, adicionar pagamento ou ativar publicação.

Um handshake bem-sucedido prova transporte e catálogo, não garante que a chave
execute chamadas da API nem que haja vídeo/áudio. Essa aceitação continua a exigir
o teste já registrado `20261015-rapidapi-native-j2rk8ycXe3c-0-40-v1`, preservando
o ID e o resultado antes de qualquer retomada. Não reiniciar testes anteriores.

Teste local, sem rede:

```sh
python3 -m unittest discover -s migration/diagnostics/rapidapi-mcp -p test_connection_probe.py -v
```
