# HeroVerse — transferência para o próximo chat

Checkpoint preparado em 23/10/2026 UTC, ainda noite de 22/10 em Brasília. Esta é uma transferência de execução, solicitada por Matheus, não uma aprovação nem uma ativação da produção. Confira o GitHub atual antes de agir: automações preexistentes continuam escrevendo no repositório.

## 1. Resultado que o usuário quer

Concluir um robô de canais sem apresentador, usando o HeroVerse como piloto: mineração audiovisual de mercado → modelagem e produção original → originalidade, intenção e crítica → publicação completa → medição e aprendizado. O nicho atual é conteúdo cristão original em inglês: fé, oração e reflexão. Longos e Shorts fazem parte do mesmo ciclo.

Matheus quer etapas claras, com entrada, entrega e aceite; execução em nuvem, sem depender do computador dele; custo adicional zero e capacidade gratuita recorrente; poucas tarefas simultâneas e resultados reais. Não quer outra arquitetura, mais documentos ou PRs apresentados como se fossem vídeos aprovados. O objetivo comercial é validar e depois vender o sistema. Prazo de monetização é uma meta, nunca uma previsão comprovada.

Diretriz mais recente: aprender com defeitos verdadeiros e corrigir a modelagem **antes** de produzir os próximos vídeos. O ciclo desejado é problema comprovado → causa na produção → alteração concreta → resultado comparável → prevenção na próxima modelagem. Referência bem avaliada não garante automaticamente a nota do resultado. Não otimizar o prompt do revisor para obter notas maiores.

## 2. Repositórios, contas e autorização

- Engine público: https://github.com/matheusmagah-cpu/heroverse-engine
- Runner público: https://github.com/matheusmagah-cpu/heroverse-runner
- Responsável pelo projeto: Matheus. Conta do canal: Will. Canal: https://www.youtube.com/@heroverse74 — ID `UCuMF6pJQkyMzaVoAxFL86yA`.
- A conta do YouTube não prova, por si, a titularidade de uma chave Gemini. Nesta sessão houve uma verificação específica da credencial existente e do projeto; veja a seção de custo.
- O usuário já autorizou continuar, corrigir e limpar o projeto. Não pedir novamente autorização genérica para cada ação rotineira. Respeitar custo zero, permissões efetivas, critérios congelados e os limites de publicação.
- O usuário confirmou especificamente a declaração de direitos e o uso secundário do arquivo enviado ao Google AI Studio para desenvolvimento/melhoria de produtos. A confirmação foi aceita. Não perguntar novamente pela mesma declaração para o mesmo envio.
- Não foram criadas/rotacionadas chaves, contratado serviço, ativado faturamento ou concedida aprovação manual do vídeo. Uma nova ampliação de acesso ou novo acordo continua exigindo tratamento próprio.
- Nunca publicar chaves, cookies, URLs OAuth completas, e-mails pessoais, identificadores de projeto ou fingerprints de credencial em novos recibos públicos. Preservar segredos no mecanismo configurado.

## 3. Git confirmado e ordem de leitura

Antes de adicionar esta transferência, `main` foi consultada ao vivo em 23/10 às 00:25 UTC:

`e132ea748f1b2e97713ba4c0e4516ae56fdbaaf7`

Depois do checkpoint anterior `c9bb7d783ce322b11db965d24c7fc82418123741`, havia exatamente dois commits:

| Commit | Alteração |
|---|---|
| `7330a01a6504a08cd4a61eb54c8c15afe8128d5a` | Registro de ERROR do piloto 010, run `39840108075` |
| `e132ea748f1b2e97713ba4c0e4516ae56fdbaaf7` | Novo registro de ERROR do piloto 010, run `39866986436` |

Ambos só alteraram `pilot-010/out/critique.json` e `out/review.json`. Não revisaram o Short 006 nem entregaram uma nova rota. O ERROR mais recente do 010 está registrado às 22:47:27 UTC de 22/10. Uma crítica textual PASS não equivale a revisão audiovisual PASS.

Leia nesta ordem:

1. Este arquivo e diferenças posteriores ao commit que o contém.
2. `migration/SYSTEM.md` — contrato canônico das quatro etapas.
3. `migration/OPERATIONS.md` — execução, ferramentas, automações e resultados reais.
4. `migration/STANDARD.md` e `migration/strategy/MODELING_SPEC.md` — critérios e limitações das medições.
5. `migration/evidence/reviewer-qualification/20261022-aistudio-short006-validation.json` e os dois JSON brutos nele referenciados.
6. Os recibos de projeto, preflight, Interactions, inline e stable no mesmo diretório.
7. `migration/production/pilot-006/shorts/shorts.json` e a issue #259.

`CUTOVER_STATUS.md`, recibos de 14/15 de outubro e o relatório antigo do Dot são históricos. Se tiverem sido arquivados, localizar pelo inventário; não restaurá-los como autoridade atual. A issue #259 e textos de handoff anteriores podem estar atrasados em relação aos recibos desta sessão.

## 4. O bloqueio atual, sem ambiguidade

**Ainda não foi obtida uma revisão audiovisual válida do master atual do Short 006. Nenhuma alternativa foi qualificada para assumir a produção.**

As APIs testadas responderam 503. O teste de interface retornou 8,9, mas essa resposta foi invalidada por incompatibilidade com o conteúdo: falas inexistentes e marcações erradas. A resposta não foi incorporada ao manifesto, não autorizou publicação e não deve alimentar ajustes de produção.

O teste seguinte solicitou apenas prova de acesso ao conteúdo. O modelo declarou que não tinha acesso aos frames nem ao áudio. Isso é uma declaração do modelo, não um trace de transporte; somada às discrepâncias objetivas, impede qualificar a revisão anterior. O player visível prova reprodução na página, não recepção pelo modelo.

O último envio corretivo teve timeout da ferramenta. Seu resultado é **DESCONHECIDO**, não sucesso nem falha comprovada do provedor. Inspecionar o estado existente antes de qualquer nova tentativa.

## 5. Identidade do master preservado

| Campo | Valor |
|---|---|
| Arquivo interno | `short-00.mp4` |
| SHA-256 | `d6a7dc7024f6660c87a93d87db6a55d4073048e05f4728c043b1fc70229566b4` |
| Bytes | `15369406` |
| Duração | 42,0 segundos |
| Vídeo | 1080×1920, 30 fps, 1260 frames |
| Release asset | `662430977` |
| Release/tag | `v0.0.0-cloud-assets-20261013` |
| Manifesto | `migration/production/pilot-006/shorts/shorts.json` |
| SHA-256 do manifesto consultado | `cc8daa14d106a4e09fd9cede224a8edf2e9c6a903a13e9d5e02f909709a4a701` |

Asset:
https://github.com/matheusmagah-cpu/heroverse-engine/releases/download/v0.0.0-cloud-assets-20261013/pilot-006-short-00-sha256-d6a7dc7024f6660c87a93d87db6a55d4073048e05f4728c043b1fc70229566b4.mp4

QA existente: sete controles técnicos PASS; áudio -15 LUFS e -2,4 dBTP; verificações acústicas PASS. Preservação do áudio do material anterior comprovada por pacotes AAC/PCM. Esses resultados foram reutilizados; não repetir QA, ASR, render, calibração GOP300, revisão de frames ou referência musical sem mudança relevante no material ou no critério aplicável.

A versão antiga `96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e` recebeu **8,3**, com ritmo 6,8. Seu histórico está em `correction-history-96c8268f.json`. O 8,3 não pertence ao master atual. O manifesto local antigo do Dot não deve sobrescrever o canônico.

Último resultado canônico do master atual: run `39597248682`, 21/10, dois HTTP 503, espera de 20 s entre eles, nenhuma espera após a última falha, cleanup SUCCESS; `NOT_REVIEWED_ProviderFailure`, `publish=false`. `finalization.status=COMPLETE` só encerra a execução. O Short não aparece no ledger como `short:pilot-006`; o longo 006 é outro vídeo.

## 6. Custo, credencial e capacidade

`20261022-runtime-preflight.json`, run `39779111955`, confirmou a correspondência da credencial em runtime com a política existente e o vínculo manifesto/QA. Não fez inferência.

`20261022-project-binding.json`: observação direta às **16:07:12.382 UTC de 22/10**, validade até **16:07:12.382 UTC de 23/10**. A sessão confirmou o projeto contendo a credencial existente, Free tier e nenhuma conta de faturamento. Fechou a lacuna anterior de associação para essa observação; não exige trocar/criar chave. O recibo público foi sanitizado.

Limites exibidos para o modelo designado: **5 RPM, 250.000 tokens de entrada/minuto, 20 requisições/dia**, por projeto. O painel tem atraso; pico observado não é saldo reservado. Uma leitura posterior mostrou pico de 8 RPD; isso não é garantia de disponibilidade.

Dois longos e três candidatos de Short por longo representam nominalmente oito decisões/dia, ou 16 com uma repetição por decisão, antes de backlog, correções e outras chamadas. Não há demonstração de capacidade recorrente do pipeline inteiro nem orçamento global de todas as chamadas. A observação de Free tier não torna o serviço infalível ou gratuito para sempre. Se a observação vencer, renovar só o necessário antes de efeitos que dependam dela.

## 7. Qualificações de API realmente executadas — não repetir inalteradas

Todas preservaram o modelo `gemini-3.8-flash`, o MP4 completo com áudio, os limiares e a identidade do arquivo. Produção continua usando `generateContent`; as rotas abaixo são isoladas.

| Rota | Run / resultado | Recibo |
|---|---|---|
| Interactions beta com URI do arquivo | `39816315756`, 16:43 UTC; uma inferência 503; cleanup SUCCESS | `20261022-interactions-short006.json` |
| Interactions beta com vídeo inline | `39822372027`; texto READY 200 em 244,8 s; MP4 inline 503 em 5,5 s; duas chamadas | `20261022-inline-diagnosis-short006.json` |
| Interactions estável v1 | `39825632213`, 17:46 UTC; controle de texto 503 em 0,45 s; chamada de vídeo corretamente omitida | `20261022-stable-diagnosis-short006.json` |

Reservas STARTED consumidas: `12441419008`, `12445042034`, `12446885743`. Qualificações: `short006-20261022-interactions-v1`, `short006-20261022-inline-diagnosis-v1`, `short006-20261022-stable-inline-v1`. Não apagar reservas nem trocar só o identificador para repetir a tentativa.

Artefatos finais: `12442217461`, `12444883451`, `12447000483`, respectivamente. Os recibos preservam hashes e detalhes. Resultado do modo inline mostra que o problema não está limitado à resolução da URI do Files API. A falha do controle de texto mostra que houve falha também sem o vídeo. Nenhum resultado isola a causa exata ou prova indisponibilidade global.

Documentação e respostas oficiais do Google consultadas tratam 503 como possível sobrecarga temporária. Isso apoia a hipótese, não prova a causa de cada solicitação. Na interface, às aproximadamente 23:44 UTC, apareceu `Settings (Partial service outage)`; foi apenas uma observação de UI, sem investigação adicional do incidente.

## 8. Teste do AI Studio e descoberta que não pode se perder

URL de trabalho: `https://aistudio.google.com/u/1/prompts/new_chat` — é URL de conversa nova, não endereço persistente da avaliação.

O arquivo exato foi verificado localmente antes do envio. A interface mostrou vídeo de 42 s com `readyState=4` e sem erro de decodificação. Também havia `Token count failed` e a amostra de código exportável não demonstrava o anexo. Essas observações não provam o payload efetivo.

Configuração da avaliação: Gemini 3.8 Flash, thinking Medium, output 4096, resolução Default, fps 1, vídeo inteiro; schema JSON com os mesmos nove itens; buscas, código, funções, Maps e URL context desligados; prompt original do revisor com o hook `Let your face soften.`.

Às **19:05 UTC**, a UI retornou overall 8,9. Arquivo bruto: `20261022-aistudio-short006-response.json`, SHA-256 `d12745205101e1ed659e20bf6ecf9a5b25ace5be5260c0521e12f5d2bb9d5175`.

Contradições verificadas contra texto e timing canônicos já aprovados:

| Afirmação da resposta | Conteúdo do master registrado |
|---|---|
| Final em 0:21 com “Bring your awareness back...” | Em 20,977–22,407 s: “You are held.”; o final falado é “Rest now.” em 39,367–40,689 s |
| “release the tightness in your forehead, let your jaw drop” no início | O início é “Let your face soften. Let your eyes close. Let your shoulders drop.”; as falas citadas não existem |
| Transição entre paisagens em 0:12 durante retenção de respiração | A transição principal é planejada em aproximadamente 20,977 s; não há instrução de prender a respiração no texto |

Às **19:11 UTC**, uma sondagem de acesso pediu duração, falas finais e objetos em cenas sem fornecer as respostas. O modelo declarou não ter acesso a frames nem áudio. Resposta completa preservada em `20261022-aistudio-short006-grounding-probe.json`. Capturas recortadas preservam a UI sem a barra de conta.

**O 8,9 é resposta inválida, não nota audiovisual do master e não motivo legítimo para alterar encerramento ou ritmo.** O assistente chegou a anunciar 8,9 em atualização intermediária, mas depois verificou e corrigiu essa interpretação. Não perpetuar o primeiro anúncio como aprovação parcial.

Depois foi tentado um envio em conversa limpa, após a declaração de direitos ter sido aceita. A ferramenta foi interrompida. Na recuperação, havia popup de seleção da conta Google para o fluxo de upload; foi selecionada a mesma conta já autorizada. O popup fechou e o AI Studio mostrou a conta autenticada, mas nenhum arquivo anexado. Não foi observada nem aceita uma nova tela de concessão de permissões. Não inferir os escopos efetivos a partir desse fechamento.

A tentativa seguinte de abrir o seletor e anexar o arquivo terminou com **`timed out awaiting tools/call after 300s`**, apesar de timeout menor solicitado pelo cliente. Não foi executada uma nova inferência após isso. O estado final de upload é desconhecido. Não usar essa falha da ferramenta como prova de falha do MP4 ou de bloqueio de segurança do site.

## 9. Código entregue e código que ainda não existe

Entregas recentes já incorporadas:

- PR #268: arquivamento do caminho Kaggle.
- PR #269: limpeza estrutural completa dentro do escopo inventariado; 1.699 caminhos do engine e dois do runner, 287 Python examinados por AST, 153 arquivos arquivados mantendo bytes e quatro `.pyc` removidos. Não significa auditoria funcional integral de cada módulo. Ver `migration/archive/ARCHIVE_PLAN.json`.
- PR #270: contrato de etapas e mapa operacional. Não adicionou um orquestrador.
- PR #271: preflight isolado.
- PR #272, merge `66b1d772a59a4e4cbe29f9cf9c441049b4ec3ad1`: qualificação Interactions do master preservado, identidade, custo e reserva durável.
- PR #273, merge `fc863d0492be8c215bca306969c09b36df593c79`: controle de texto e diagnóstico inline.
- PR #274, merge `a3ba3d46b3d57c31a0f430dedbaf8d586592a3a3`: candidato v1 estável e correção da preparação de dependências do CI. Run `39824476302`: 51 arquivos de teste PASS. Isso não é 51 testes de vídeo nem disponibilidade de provedor.
- Runner PR #8: ajuste de metadados; executor continua necessário.

Arquivos centrais:

- `.github/workflows/reviewer-preflight.yml`, `migration/production/reviewer_qualification.py`, `test_reviewer_qualification.py`.
- `migration/production/shorts_review.py`, `shorts_006_plan.py`, `shorts_006_material.py`, `shorts_006_motion.py`.
- `migration/mining/structure_mining.py` — transporte compartilhado.
- `migration/production/long_review.py` e `migration/publish/prepublish_gate.py` — longos.
- `migration/publish/owner_quality_policy.py`, `pending_shorts.py`, `publish_shorts.py` — piso e elegibilidade.
- `migration/mining/learning_loop.py`, `owned_feedback.py` — relatórios de aprendizado/medição.

O protótipo antigo do Dot, relatado como “50 testes”, desapareceu de `/tmp`; nunca fez inferência real. Não confundi-lo com a implementação entregue nesta sessão, nem com os 51 arquivos de teste do CI.

O `reviewer-preflight.yml` isola o teste: permissões de leitura, sem credenciais YouTube, sem alteração canônica e `publish=false`. Os modos consumidos não são comandos de retomada prontos. `shorts-review.yml` e `shorts.yml` têm efeitos adicionais e caminhos históricos do 006 consumidos/expirados. `approve.yml` pode disparar publicação/Shorts; não usá-lo como diagnóstico isolado.

## 10. Aprendizado na modelagem: requisito novo e lacuna real

O contrato de etapas já pede retorno de melhorias. Porém a implementação atual de `learning_loop.py` é **report_only**: produz HOLD/KEEP_EXISTING_PENDING_EVIDENCE, registra insuficiência de checkpoint, baseline e atribuição de estrutura. `script_mutation=false` e `rendered_inputs_mutation=false`. Não alegar que existe ajuste automático de modelagem funcionando.

Para implementar a diretriz do usuário, integrar o retorno nos arquivos/fluxos existentes, sem criar um segundo orquestrador:

1. Aceitar apenas revisão válida do arquivo exato, com motivo verificável no áudio/imagem ou instrumento qualificado. Falha HTTP, resposta sem mídia ou fala inventada volta para a etapa de revisão.
2. Ligar cada defeito à decisão que o produziu: texto, dicção, pausa, enquadramento, repetição de imagem, movimento, transição, mix, promessa ou encerramento. Separar hipótese de causa comprovada.
3. Registrar alteração concreta no roteiro/plano/geração/edição, com trecho, arquivo e teste de aceitação; incorporar a prevenção antes do próximo render do mesmo formato.
4. Reavaliar material realmente alterado com os critérios congelados. Conservar rejeição anterior, mudança e nova identidade; observar se o defeito desapareceu. Não repetir avaliação até obter nota conveniente.
5. Avaliar eficácia: taxa de aprovação na primeira revisão, defeitos repetidos, retrabalho por vídeo; depois retenção, CTR e resultados por idade comparável. Melhor nota não garante resultado comercial.

O caso 8,9 deve ficar fora dos exemplos de qualidade usados para aprender. Ele é um exemplo de falha do revisor/acesso à mídia.

## 11. Próxima ação concreta e critério de conclusão

Trabalhar primeiro no handoff audiovisual, uma etapa de cada vez:

1. Reconciliar `main`, worktree, recibos e jobs ativos. O relógio e a validade da política podem ter avançado. Não repetir verificações aprovadas ainda aplicáveis.
2. Inspecionar, uma vez, o estado do upload interrompido na sessão existente se ela estiver disponível. Não depender de IDs antigos de tabs nem considerar um player como prova de envio. Se o navegador continuar travando, registrar o bloqueio e não entrar em loop de upload.
3. Só executar inferência após uma correção concreta do envio/recepção ou condição verificável de recuperação do provedor. Exigir evidência de áudio e imagem antes de atribuir uma nota. Uma sondagem de conteúdo não substitui a revisão completa.
4. Qualificar a rota com os controles já definidos. A UI manual, mesmo que passe a funcionar, não comprova integração automática ou capacidade recorrente. Uma alternativa de modelo também precisa da calibração; não trocar só para receber uma resposta.
5. Para o master preservado, obter uma revisão real, completa, vinculada ao SHA, com modelo, rubrica, horários, resultado e limitações de origem. Não inventar HTTP 200 para uma resposta da UI.
6. Somente depois tratar defeitos reais e fechar pacote de liberação com horário novo. O slot e prazo de 21/10 venceram.

Etapa concluída exige: acesso nativo comprovado a imagem e áudio, revisão válida e identidade preservada, custo adicional zero verificado para a configuração real, capacidade recorrente demonstrada para a carga e integração operacional qualificada. Código verde, login, documentação, metadados ou resposta JSON isolada não encerram a etapa.

## 12. Pendências seguintes, depois da revisão

| Material | Último estado conhecido; reconsultar antes de agir |
|---|---|
| Longo 006 | 9,3 e publicado; não confundir com o Short |
| Short 006 | QA aprovado; revisão canônica ausente; resposta UI 8,9 inválida |
| 008 | QA PASS; revisão 8,0/ritmo 6,5; glitch 13:34, “GOD” pronunciado em letras 17:36, pouca variedade |
| 009 e 011 | Reprovação do intervalo entre repetições de imagem; exigem correção de material/plano |
| 010 | QA PASS; revisão 503, inclusive nos dois novos registros do dia 22 |
| Shorts 007 | Reprovações 7,5 e 7,8 ou revisão não concluída |
| 012 | Longo histórico 8,8 enviado sob padrão anterior; Shorts sem elegibilidade |
| Short 005 | Publicado com exceção específica de 8,5; não reduz piso futuro |

Ainda não há estoque futuro aprovado suficiente. A ordem é corrigir defeitos, formar estoque aprovado, concluir pacote/reconciliação, medir 48 h e sete dias, e só então escalar formatos/canais. Publicação inclui descrição, capítulos, captions, playlist, divulgação de IA e pendências de comentário/telas finais; API não faz tudo, verificar cada entrega. Nunca reenviar vídeo só porque a reconciliação está incompleta.

Mineração: oração guiada com paisagens atende a amostra interna; outros formatos seguem candidatos/parciais. Detector de cenas apresentou aproximadamente 58% contra requisito de 90%; transcrição 75% contra 80%; instrumentos/modelagem/originalidade ainda têm pendências. Especificações de ritmo contêm avisos sobre janelas de transcrição defeituosas: estimativas não viram medidas aprovadas por repetição. Capacidade cinematográfica gratuita nativa 1080p e animação 6–10 s (#183) não foi encerrada.

## 13. Evitar retrabalho e problemas já conhecidos

- VideoDB: US$20 iniciais, sem renovação mensal comprovada; duas importações “Failed to fetch”. Não adotar como gratuidade permanente nem repetir sem correção.
- YouTube direto não demonstrou frames/áudio. Erro 153 em `/embed` aberto diretamente não prova que iframe hospedado corretamente falhe. Não recontar esse teste como diagnóstico conclusivo.
- Oracle descartada por não resolver acesso audiovisual. Não retomar cadastro/migração.
- Backups Gemini/locais já testados não se qualificaram: Flash Lite teve aprovações indevidas de defeitos; Flash 3.6 rejeitou controles e teve falhas; SmolVLM2/Whisper não cumpriu pré-requisitos ASR e não equivale a revisão audiovisual nativa completa.
- Não remover runner, mídia, fonte original, instrumentos ativos, histórico, ledger ou reservas por parecerem excedentes. O inventário de limpeza documenta o que foi arquivado.
- A pausa do agente não desliga crons. Houve revisões automáticas do 010 durante a pausa. Não declarar produção/supervisão globalmente desligadas.
- Há hipótese de que `render_queue.py` trate Short sem PASS/FAIL como candidato a `shorts.yml`, podendo reiniciar produção por erro de revisão. Isso foi lido, **não corrigido nem demonstrado como ocorrência no 006**. Verificar guardas e seleção efetiva antes de alterar. O 006 tem longo já enviado e condições próprias.
- GitHub retornou estados de runs em cache. Leituras ao vivo com query única e logs concluídos resolveram a divergência; não reexecutar job por um status resumido atrasado.
- Não criar testes repetindo a implementação ou QA de mídia intacta. Testar mudanças reais e cumprir gates aplicáveis; parar testes opcionais após risco resolvido.

## 14. Arquivos locais e continuidade

Workspace usado: `/workspace/scratch/f2180567de8e/heroverse-engine`; runner em diretório irmão. MP4 temporário: `/workspace/scratch/f2180567de8e/short006-preserved.mp4`. Esses caminhos podem desaparecer. A release remota e os arquivos versionados são a continuidade confiável.

As duas respostas UI, as capturas e o recibo de invalidação acompanham este documento no commit de transferência. Não reaplicar como mudanças inéditas. A branch local foi atualizada em fast-forward com os dois registros do 010 antes deste checkpoint.

Não continuar a execução de inferência nesta transferência. O próximo chat deve começar reconciliando o que existe, dizer qual é a próxima ação demonstrável e executá-la dentro das autorizações. Atualizações curtas e factuais para Matheus; nada de dizer “resolvido”, “ativado” ou “aprende sozinho” sem a entrega correspondente.
