# Protocolo do operador: NÃO entregar ao avaliador

## Objetivo e escopo

Triagem mínima de acesso audiovisual na interface escolhida e de discriminação entre alinhamento e desvio de aproximadamente meio segundo. Estes controles não são uma avaliação geral do modelo. Acesso de uma API a vídeo não implica automaticamente acesso da mesma API ao áudio. Revalidar na interface e configuração reais que serão usadas.

Nenhuma tentativa de inferência, upload, download, compra ou avaliação de provedor foi executada na preparação. Só há dados sintéticos locais.

## Preparação de uma avaliação futura

1. Obter a autorização necessária para envio dos arquivos ao destino desejado antes de qualquer upload. Esta preparação não concede autorização de envio.
2. Usar apenas os MP4 de `stimuli/` e o texto neutro de `evaluator-prompt.txt`. Não incluir esta pasta, scripts, README, hashes ou qualquer resultado esperado no contexto do avaliador.
3. Embaralhar a ordem e atribuir novos nomes opacos antes de um teste real; guardar a correspondência apenas no lado do operador. A numeração atual foi arbitrária, mas é fixa e não serve como segredo após divulgação.
4. Preferir uma tentativa independente por arquivo, sem respostas anteriores, pistas ou correções entre casos. Usar a mesma instrução, modelo, versão, configurações e via de upload para os cinco.
5. Registrar o canal de acesso realmente oferecido pela interface, a resposta literal e a decisão por arquivo. Um arquivo rejeitado ou canal inacessível é limitação da configuração, não evidência de que o modelo ouviu silêncio.
6. Julgar primeiro pelos eventos observados e por sua relação, sem aceitar apenas a afirmação “consigo ouvir”. Respostas podem ser adivinhadas, contaminadas ou derivadas de ferramentas; este conjunto não prova o mecanismo interno de acesso.
7. Guardar a conclusão estritamente no escopo testado. Qualquer resultado negativo ou indeterminado impede declarar o acesso audiovisual validado para a tarefa seguinte. Passar todos os itens só sustenta “passou estes controles sintéticos nesta configuração”.

## Gabarito resumido

- `c01.mp4`: três flashes em 1, 3 e 5 s; três tons aproximadamente 0,5 s depois dos flashes.
- `c02.mp4`: imagem constante; três tons em aproximadamente 1, 3 e 5 s. Não há referência visual transitória para declarar sincronização.
- `c03.mp4`: três flashes em 1, 3 e 5 s; áudio digitalmente silencioso. Todo o PCM decodificado é exatamente zero.
- `c04.mp4`: três flashes e três tons alinhados em aproximadamente 1, 3 e 5 s.
- `c05.mp4`: três flashes em 1, 3 e 5 s; três tons aproximadamente 0,5 s antes dos flashes.

A imagem decodificada dos quatro casos com flashes é idêntica, impedindo distinguir seu áudio a partir de diferenças visuais entre as variantes. O caso sem flashes é constante em todos os 180 quadros decodificados.

## Critérios conservadores

- Acesso visual: distinguir três flashes de imagem constante.
- Acesso sonoro: distinguir silêncio observado de três tons; reconhecer os tons também com imagem constante.
- Relação audiovisual: distinguir alinhado, som antes e som depois nos três pares aplicáveis. Não atribuir sincronização ao silêncio ou à imagem constante.
- Não exigir números em milissegundos. Se houver estimativa numérica, alinhado dentro de ±0,15 s e desvios entre 0,3 e 0,7 s com o sinal correto são critérios de triagem, não limites psicofísicos nem métricas de precisão.
- Relato honesto de canal indisponível: resultado indeterminado de acesso, não falha perceptual nem passe.
- Não agregar numa nota média que esconda o fracasso de um canal. Registrar cada requisito e cada arquivo separadamente.
- Sem música, fala, semântica, narrativa ou decisão de aprovação de conteúdo neste conjunto.

## Evidência objetiva local

`manifest.json` contém tamanho e SHA-256 de cada MP4, formato, perfil, duração, contagem de quadros, hashes de pixels decodificados, PTS, silêncio exato, onsets pós-AAC e frequências estimadas.

`frame-measurements.json` contém a média da região central por quadro e os índices de flash.

`pts-evidence.json` contém PTS de todos os quadros de vídeo, PTS e contagens de amostras dos quadros decodificados de áudio e PTS/DTS/duração/dados de descarte dos pacotes de áudio.

`probe-evidence.json` contém a inspeção completa de formato e trilhas via ffprobe.

`reproducibility.json` registra a comparação SHA-256 entre duas gerações independentes no mesmo toolchain.

`negative-tests.json` registra se trocas deliberadas de condição foram detectadas pelo verificador.

`SHA256SUMS.stimuli` permite conferir os arquivos com `sha256sum -c operator-only/SHA256SUMS.stimuli`, executado a partir da raiz do conjunto.
