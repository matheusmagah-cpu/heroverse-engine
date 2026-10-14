# HeroVerse — contrato de previsibilidade baseada em evidência
Decisão do proprietário em 14/10/2026. Complementa os contratos existentes; não é aprovação de produção, calibração ou garantia de audiência.

## Uma direção para todo o projeto
Mineração observada → mecanismo/modelo com evidência → contribuição original → roteiro/TakePlan → QA → publicação autorizada → resultado oficial → comparação com a previsão → melhoria medida. Usar o Gestor, fila, ledger e registro de regras existentes; nenhuma ferramenta mantém estratégia paralela. Uma etapa não pode substituir uma lacuna da anterior por uma afirmação de IA.

## O que a estimativa de audiência deve conter
Identidade do canal/vídeo/formato e versão, instante de corte, origem dos dados, métrica e unidade, janela e horizonte, previsão central e intervalo, cenário de referência, amostra e exclusões, premissas, limitações e condições de invalidação.
- Visualizações: reproduções, não quantidade de pessoas.
- Espectadores únicos: métrica própria autorizada; não converter views em pessoas.
- Inscritos: ganho líquido separado da contagem total.
- Horas e receita: Analytics, contadores YPP qualificados e receita efetiva são grandezas distintas.
Cada métrica só recebe estimativa quando sua base aplicável existir. Campo indisponível é null/UNAVAILABLE, nunca zero ou um valor inventado. Horizonte de 24h, 7d ou 30d exige resultados comparáveis nesse mesmo horizonte; lifetime e janela parcial não substituem resultado de D7.

## Base permitida e fronteiras
Comparar idioma, público/mercado observado, família, duração, idade de publicação, escopo de tráfego e condições de produção. Não extrapolar a audiência de um canal grande para HeroVerse por copiar estrutura. Mercado público pode fundamentar um cenário de demanda; não fornece CTR, retenção, RPM nem conversão privada de concorrentes.
Usar vencedores, medianos e fracos, incluindo evidência contrária e saturação. Título sugere tema; observação audiovisual confirma mecanismos e entrega. Temas e subtemas novos precisam de evidência; a diferença substantiva do roteiro próprio fica declarada.

## Precisão verificável
Previsão registrada ANTES da janela de resultado, dados limitados ao corte e avaliação em resultados não usados para ajustar essa previsão. Comparar erro absoluto, erro relativo quando o denominador permitir, cobertura/largura de intervalos e resultado frente ao baseline. Evitar divisão por zero e tratar baixas contagens explicitamente.
Uma faixa contendo 90% dos valores de três exemplos não demonstra cobertura de 90% em vídeos futuros. Rótulos de precisão, confiança ou calibração exigem avaliação aplicável. A meta de precisão deve ser pré-registrada por métrica/domínio, não escolhida depois para aprovar o modelo.
Monitorar drift e recalibrar ou retirar o modelo quando a evidência deteriorar. Não prometer previsibilidade perfeita do algoritmo, viralização, monetização ou longevidade.

## Melhoria e sustentabilidade
Observação oficial → defeito pontual → hipótese falsificável → uma variável controlada → execução dentro dos gates → medição posterior de mesma idade/escopo → adoção/rejeição/INCONCLUSIVE. Adaptação ao mercado não pode apagar o experimento ativo ou misturar longos, Shorts e música.
Retorno de audiência, satisfação, retenção, conversão, saturação e recorrência são monitorados quando mensuráveis. Média não compensa gate crítico. Ausência de dados não comprova que o canal está saudável nem que morreu.

## Achados e estado real
1. Pesquisa sonora nativa está limitada a duas famílias e dois tratamentos fixos. Não implementa descoberta semântica aberta de temas novos.
2. VideoMining contém tema/ângulo/tese com claims; subtopics são strings opcionais sem vínculo individual obrigatório. Sucessor precisa de proveniência por subtema, não apenas tags.
3. build_prediction aceita lista de números, fixa coorte broll STANDARD e pode rotular CALIBRATED_OUT_OF_SAMPLE sem verificar ali proveniência ou avaliação. A trava versionada em migration/runtime_bridge/prediction_provenance_guard.py bloqueia essa rota; foi testada em shadow, não instalada no runtime.
4. As oito leituras privadas atuais têm diferentes janelas de vida e formatos; não são oito resultados D7 homogêneos. A coleta de 13/10/2026 contém apenas uma leitura por vídeo nessa consulta. Não há base demonstrada para estimativa calibrada da audiência futura do master de 3h.
5. Estimativa calibrada atual do HeroVerse: UNAVAILABLE. Não é previsão de zero audiência.
Integração do sucessor semântico, avaliador preditivo, instrumentos de qualidade e worker independente permanece pendente. Estes requisitos estão registrados; nenhuma implementação completa ou publicação é declarada por este documento.
