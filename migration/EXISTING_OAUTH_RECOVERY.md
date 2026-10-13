# HeroVerse — reutilização da autorização existente
Atualizado em 13/10/2026 após leitura da documentação e correção do proprietário.

## Evidência existente
HeroVerse_Projeto_e_Continuidade.md, versão23:
- D-068: consentimento Wellisson, quatro escopos e token externo; projeto Google graphic-tide-490010-u9.
- D-071: HeroVerse Channel Operations em produção, uso pessoal; configuração e branding concluídos.
- D-072: token espelhado, refresh não interativo e canal UCuMF6pJQkyMzaVoAxFL86yA verificado; continuous_operation_ready=true, DURABLE_POLICY_CONFIGURED.
- D-074/D-075: seleção explícita da conta em reautorização; refresh não interativo e saúde HEALTHY documentados.
- Pacote posterior registra conexão e durabilidade válidas no ambiente Windows original.
Esses registros provam configuração e funcionamento histórico; não provam acesso atual do executor cloud ao segredo.

Cliente informado pelo proprietário: 663335615694-gs2ivqgl5iaaed44cv3fpvpcfcamnnch.apps.googleusercontent.com.
Não usar ID isolado como autorização nem confundir com API key.
Conta YouTube: willmarquesfotografia@gmail.com. GitHub continua separado.

## Bloqueio observado
Neste ambiente ChatGPT: HERO_YT_TOKEN_PATH, HERO_YT_OAUTH_CLIENT_PATH e HERO_YT_RECONSENT_SOURCE_PATH não configurados.
Isso não constitui inventário dos secrets do GitHub nem prova de ausência em outros ambientes.
Inventário read-only em13/10/2026: dispositivo Matheus 96bd1ae2-e3d1-464c-8111-f8df5733f89d Offline, último contato8h antes. Não houve tentativa de conexão/execução no dispositivo offline.
Código e documentação guardam token fora de workspace/repositório. O arquivo fonte transferido exclui esse segredo intencionalmente.
Google Cloud inacessível neste navegador é bloqueio de UI, não evidência de falta de autorização Google.

## Próxima ação correta
1. Conferir localização canônica e configuração do segredo existente, inclusive eventual provisionamento cloud, sem imprimir valores.
2. Recuperar ou transferir o token já autorizado por canal seguro quando sua origem estiver acessível.
3. Armazenar fora do código, com acesso restrito ao executor.
4. Executar a prova original de refresh e channels.list(mine=true), exigir ID exato e ordem/hash dos receipts.
5. Reconectar somente se a prova identificar revogação/escopos insuficientes ou segredo irrecuperável.
Não criar outro cliente nem repetir branding/consentimento como primeira opção.
Não solicitar senha/OTP/refresh token no chat, salvar segredos em documentação, extrair cookies ou enfraquecer gates.
Nenhuma credencial foi recuperada ou instalada nesta revisão; produção continua desativada.

## Regra permanente de execução
Antes de propor recriação, revisar documentação atual, código, receipts e configuração do destino.
Reutilizar provas válidas e recursos existentes; resolver somente o delta da migração.
Distinguir histórico comprovado, estado observado agora e hipótese ainda não verificada.
Não repetir testes equivalentes sem alteração/falha nova. Não confundir testes de fixtures com operação real.
O proprietário requer precisão, aceleração e ausência de retrabalho.
