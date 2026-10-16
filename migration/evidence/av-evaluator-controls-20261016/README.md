# Registro offline de triagem audiovisual

## Resultado

ROTA/CONFIGURAÇÃO NÃO QUALIFICADA. Ingestão audiovisual pelo backend NÃO VERIFICADA.

Escopo: cinco controles sintéticos submetidos uma vez cada ao Google AI Studio Playground, pelo Chromium cloud, com o rótulo de modelo observado `gemini-3.8-flash` e a configuração registrada em `observations/ai-studio-observations.json`. O registro contém cinco respostas e zero repetição de inferência. Esta análise não invocou modelo, reexecutou ensaios ou enviou o gabarito.

Todos os ensaios registraram `Token count failed`. Player local com duração de 6 s, `readyState=4` e sem erro não comprova recebimento ou decodificação audiovisual pelo modelo. Não há recibo de ingestão do backend nem URL durável verificada de cada conversa. A causa dos resultados permanece indeterminada. Não extrapolar para toda a família Gemini, outras APIs, modelos ou configurações.

## O que registrar no Git

Este diretório contém somente texto e código, aproximadamente algumas centenas de KB:

- Receita determinística dos cinco estímulos e testes negativos do verificador.
- Prompt neutro, protocolo e manifest congelados antes das respostas.
- `operator-only/pre-evaluation-freeze.json`, preservado byte a byte; seus cinco hashes continuam conferindo.
- Cinco respostas literais e envelopes originais, sem edição.
- Observações de execução e evidências textuais da interface.
- Extração explícita das alegações por dot (assistente de IA), vinculada ao SHA-256 de cada resposta.
- Um recibo por arquivo/capacidade e um recibo geral sem média compensatória.
- Scripts e testes de reprodução dos recibos; hashes dos arquivos do registro.

Não inclui os MP4, PCM, screenshots, arquivos compilados nem outros binários. A receita permite regenerar os estímulos localmente; os hashes originais estão no manifest. Os scripts usam caminhos relativos à própria pasta. Este pacote foi preparado para registro autorizado no repositório privado; a evidência de commit e readback é mantida pelo procedimento de publicação, fora do snapshot para evitar autorreferência.

O diretório contém o gabarito e não deve ser anexado ou encaminhado a um avaliador externo. Destina-se ao registro autorizado do operador. O prompt isolado e os MP4 são os únicos materiais previstos para um futuro teste devidamente autorizado. Não publicar este pacote como parte desta preparação.

## Verificar o registro sem inferência

A partir desta pasta:

    python3 scripts/evaluate_saved_responses.py --check
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_saved_receipts.py
    sha256sum -c SHA256SUMS.record

A extração e a adjudicação semântica das respostas foram feitas por dot, um assistente de IA, e estão declaradas em `operator-only/manual-adjudications.json`. O nome `manual-adjudications.json` é histórico e não significa participação humana. Não houve revisão por pessoa humana nem revisão humana certificada. A verdade dos controles vem de medições objetivas determinísticas; a interpretação semântica das respostas é assistida por IA. O script de comparação não interpreta linguagem por conta própria: confere hashes, trechos literais e invariantes, compara campos factuais explícitos com o gabarito congelado e reproduz as decisões conservadoras.

Para regenerar mídia, preferir uma pasta temporária separada para não alterar o snapshot congelado:

    python3 scripts/build_and_verify.py --output /tmp/av-regeneration --check-reproducibility

## Limites de evidência

- O congelamento é um registro local com timestamp, preservado e hash-validado; não tem certificação externa de tempo.
- Ordem registrada: c01 a c05. O protocolo recomendava embaralhamento e novos nomes opacos por execução; não há evidência de que isso tenha ocorrido neste ensaio.
- Os nomes originais são neutros. Não há gabarito ou feedback no prompt fornecido.
- c01: seu trecho salvo de UI não contém literalmente o aviso de tokenização; esse aviso consta no envelope de resposta e no registro de execução.
- c05: a resposta final da interface foi preservada também em `observations/c05-ui-result.txt`.
- A recuperação da digitação de c03 ocorreu antes da submissão e não conta como uma nova inferência.
- As respostas podem ser comparadas ao arquivo local submetido. Sem evidência de ingestão, elas não revelam exatamente qual conteúdo chegou ao backend ou a causa da divergência.

Leia `RESULTS.md` e `receipts/evaluation-receipt.json` para o resultado completo por capacidade. Não há nota média ou porcentagem geral.

## Diagnóstico posterior de tokenização

`observations/token-count-diagnostic.json` preserva o diagnóstico de leitura, sem nova inferência ou reupload. Os caminhos absolutos dos cinco estímulos foram convertidos para caminhos relativos; o SHA-256 do registro original está documentado. O histórico exibiu um bloqueio separado de acesso ao Drive, que não foi concedido. Isso não demonstra a causa de `Token count failed`; os tabs originais já não estavam disponíveis para reinspeção.
