# Instrumento offline de atividade energética PCM16

Núcleo isolado, não integrado ao runtime. Apenas Python 3 e biblioteca padrão.
Sem rede, modelos, decodificação, mídia, fixtures externos ou dependências de
outros módulos do HeroVerse. O arquivo `audio_activity.py` é idêntico ao núcleo
testado na extensão local; a suíte aqui é independente daquela integração.

Executar neste diretório, inclusive numa cópia em diretório temporário:

```sh
python3 -I -B -m unittest discover -s . -p 'test_audio_activity.py' -v
```

`measure_pcm16_activity()` recebe bytes **PCM16 signed little-endian crus**,
intercalados em um ou dois canais, além da taxa de amostragem. Não recebe WAV,
AAC ou MP4 e não autentica o formato, origem ou hash de um arquivo. O chamador
é responsável por validar esses dados antes de usar o núcleo.

Mede janelas não sobrepostas por canal e a união das janelas ativas. O limiar
decimal e a comparação de energia usam aritmética inteira exata; não há downmix.
O resultado informa versão, parâmetros, taxa e intervalos de frames semiabertos.
A janela final usa somente os frames existentes. Os padrões são 48 frames e
RMS ≥ 0,02 de escala completa; 48 frames só equivalem a 1 ms em 48 kHz.

Os 12 testes usam PCM gerado em memória: 0/1/4 pulsos, antífase estéreo,
união por canal, limiar, tail parcial, taxa, repetibilidade e entradas inválidas.
Também demonstram que dois impulsos na mesma janela podem resultar em um único
intervalo energético: essa contagem **não é contagem perceptiva de sons**.

Sem janelas acima do limiar não significa silêncio digital ou acústico. O
instrumento não reconhece bipes, fala, música, qualidade, sincronismo audiovisual
ou significado. Não oferece análise perceptual, aprovação produtiva ou
autorização de publicação. `qualification.json` registra somente esta suíte
finita e os hashes dos três arquivos do pacote; não qualifica mídia real.
