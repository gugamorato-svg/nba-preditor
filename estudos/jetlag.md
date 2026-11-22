# Teoria: jetlag (viagem longa + pouco descanso)

## Pré-registro (escrito antes de rodar o estudo)

**Hipótese do dono:** um time que viaja uma distância longa e tem pouco descanso
rende abaixo do esperado.

**Definições, fixadas antes de olhar os dados:**

- O local de cada jogo é a arena do mandante, ou o local neutro da coluna
  `Location` (bolha de Orlando, Tampa em 2020-21, Las Vegas, Cidade do México,
  Paris, Londres etc.).
- `dias` é o número de dias desde o jogo anterior do time (1 = jogos em dias
  seguidos), pela data no fuso dos EUA.
- `fuso` é a diferença de horário entre o local do jogo anterior e o do atual,
  com o sinal positivo para o leste.
- **Variável principal:** `jet = 1` se o time cruzou **2 ou mais fusos** desde o
  jogo anterior **e** `dias ≤ 2`. `jet_diff = jet_visitante − jet_mandante`.
- Variáveis secundárias (só exploratórias, não decidem nada): distância em km
  com `dias ≤ 2`, e a direção (para o leste ou para o oeste).

**Testes:**

1. **Contra o Elo:** um coeficiente `J` (pontos de Elo por unidade de `jet_diff`)
   é ajustado só em 2019-2024, com os outros parâmetros congelados. Avaliação em
   2025-26 e 2026-27: diferença pareada de log loss com IC95 por bootstrap.
2. **Contra o mercado (o que decide se dá dinheiro):** nos jogos com preço da
   Polymarket, comparar o resultado com o preço quando o `jet` favorece um lado.
   Resíduo médio `resultado − preço` do lado favorecido, com IC95 por bootstrap.

**Critério:**

- A teoria **passa** se o IC95 do teste 2 ficar todo acima de zero.
- Se só o teste 1 passar, o efeito é real, mas **o mercado já precifica**.
- Se nenhum passar, ela **não passa**.
- Não vale trocar o limiar de fusos ou de dias depois de ver o resultado. Uma
  definição nova vira outra teoria, anotada como exploratória.

## Resultado

Rodado em 2026-11-21. **Veredito: NÃO PASSA.**

- Em 996 dos 9.756 jogos (10,2%), só um dos lados tinha jetlag.
- **Descritivo:** o lado sem jetlag venceu +1,9 pp acima do esperado pelo Elo
  (IC95 −1,0 a +4,7). O sinal vai na direção da teoria, mas pode ser zero.
- **Teste 1 (Elo):** o melhor `J` em 2019-24 foi 20 pontos. Fora da amostra
  (2025-27, 1.466 jogos), a log loss com o jet ficou −0,00024 (IC95 −0,00106 a
  +0,00063). Não melhora.
- **Teste 2 (mercado):** o lado sem jetlag venceu +1,5 pp acima do preço
  (IC95 −5,2 a +8,0, n=155). Não passa.

**Leitura:**

- O efeito, se existe, é pequeno: cerca de 1 a 2 pontos percentuais.
- Contra o mercado só há 155 jogos com jetlag. Para separar +1,5 pp de zero
  seriam precisos ~3.500 jogos assim, mais de 20 temporadas de preços.
- Mesmo se for real, 1,5 pp é menor que o custo de entrar: a taxa de taker mais
  o spread dá ~2 a 3% num preço perto de 50c.

**Exploratório (não decide, 3 variantes testadas, então ajustar por comparações múltiplas):**

- viagem para o leste: −0,2 pp (IC95 −4,3 a +3,6, n=512);
- viagem para o oeste: +4,1 pp (IC95 −0,1 a +8,2, n=484);
- 2.000+ km com até 2 dias: +2,5 pp (IC95 −0,1 a +5,1, n=1.225).

A viagem para o oeste é a única pista. Se for testada, tem que ser como teoria
nova e prospectiva: ela foi escolhida depois de ver os dados.
