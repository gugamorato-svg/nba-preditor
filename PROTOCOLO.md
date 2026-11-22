# Protocolo do teste em papel (pré-registrado)

Este arquivo foi escrito antes de existir qualquer captura em `data/paper_log.csv`.
Ele diz quando o teste acaba e o que conta como aprovado. Mudar estas regras
depois de ver resultado invalida o teste.

## O que está sendo testado

O modelo Elo da versão gravada em `data/model_params.json` (campo `version`)
contra o livro da Polymarket nos jogos da temporada regular da NBA.

## Coleta

- `python paper_collect.py` roda de hora em hora nos dias de jogo.
- Para cada jogo vale a **última captura feita 30 minutos ou mais antes do
  início**, com ask dos dois lados no livro.
- Nada é apagado de `data/paper_log.csv`. O arquivo só cresce.

## Regra de aposta simulada (fixa)

- Aposta de 1 unidade no lado em que `prob_modelo − custo ≥ 3 pontos percentuais`.
- `custo = ask capturado + 0,05 × ask × (1 − ask)`, que é a taxa de taker da Polymarket na NBA.
- No máximo uma aposta por jogo, no lado de maior vantagem.

## Quando decidir

- A decisão é **uma só**, quando a regra completar **400 apostas** simuladas
  com a mesma versão do modelo. Se a temporada acabar antes disso, o teste
  continua na seguinte com a mesma versão.
- Olhar no meio do caminho (`python evaluate.py --paper`) serve só para achar
  bug de coleta. Não vale parar antes porque "está ganhando" ou "está perdendo".

## Critério de aprovação

As duas condições precisam valer:

1. o **limite inferior do IC95** (bootstrap, 2000 reamostragens) do ROI das
   400 apostas é **maior que zero**;
2. não houve mudança de versão do modelo durante o teste.

Qualquer outro resultado é **reprovado**. Reprovado não abre "teste de novo com
outro limiar": uma ideia nova vira uma versão nova, com contagem do zero.

## Mudanças

Qualquer mudança que altere `p_model`, a regra ou o custo (parâmetros, features,
limiar, fonte de dado) gera versão nova e **zera a contagem**.

## Lesões (só observação)

Desde 2026-11-21 cada captura também grava as mudanças na lista de lesões da
ESPN em `data/injuries_log.csv`. Isso **não** entra em `p_model` nem na regra, então
não muda a versão. Serve para medir depois se a Polymarket demora a reagir a uma
notícia. Usar as lesões no modelo seria uma versão nova, com contagem do zero.

## Depois

Mesmo aprovado, dinheiro real é decisão do dono, com valor pequeno e limite de
perda definido antes. Este projeto não envia ordens e não usa carteira nem chave.
