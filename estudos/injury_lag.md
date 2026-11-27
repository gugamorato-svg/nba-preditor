# Teoria: o preço reage antes ou depois da notícia de lesão?

Issue #2. Primeira versão do script por @onlykushalll (PR #4); método e resultado
completados na revisão.

## Pré-registro (regras fixadas antes do resultado final)

**Pergunta:** quando um jogador vira "Out" na lista da ESPN, o preço da Polymarket do time
dele ainda anda **depois** da notícia, o que daria uma janela para agir, ou já tinha
andado **antes**?

**Definições:**

- **Notícia** é uma linha de `data/injuries_log.csv` em que o jogador passa a `Out`, vindo de
  outro status (Questionable, Day-To-Day…), ou entra na lista já como `Out`.
  - A primeira captura do registro não conta, porque é a lista que já existia.
  - Uma linha nova de quem já estava `Out` também não conta: a ESPN só mexeu no comentário.
- O **horário da notícia** é `espn_utc`, a atualização na ESPN.
- O **jogo** é o próximo jogo do time em `data/paper_log.csv` que começa até 36 h depois da
  notícia (o horizonte do coletor).
- **Um caso por movimento.** Notícias do mesmo time no mesmo jogo, a menos de 60 min uma da
  outra, viram um caso só, para o mesmo movimento de preço não contar várias vezes.
- O **preço** é sempre o do **time machucado**, para que "negativo" queira dizer a mesma coisa
  nos dois lados.

**Medida principal (por minuto):** histórico de preço da Polymarket (`prices-history`,
`fidelity=1`) nos 60 min antes e nos 60 min depois da notícia, cortado no início do jogo.

- antes = preço na notícia − preço 60 min antes
- depois = preço 60 min depois − preço na notícia

**Conferência (capturas de hora em hora):** a última captura do `paper_log` até a notícia, a
primeira depois dela e uma de 3 h antes. Usa o preço médio (bid + ask)/2.

- **Ela não decide:** a captura de antes pode ter quase 1 h de idade, então uma queda que
  aconteceu antes da ESPN aparece entre "antes" e "depois".

**Critério**, com 30 casos ou mais com preço por minuto (IC95 por bootstrap, 2000
reamostragens):

- **HÁ ATRASO** se a média de "depois" for ≤ −1 centavo com o IC95 todo abaixo de zero;
- **O MERCADO SE ANTECIPA** se o IC95 de "antes" ficar todo abaixo de zero e "depois" não
  passar no critério acima;
- senão, **SEM EFEITO VISÍVEL**.

Com menos de 30 casos, não há veredito.

## Resultado (26/11/2026, capturas desde 21/11)

**Veredito: O MERCADO SE ANTECIPA.** Sem janela depois da notícia da ESPN.

- 50 notícias, que viram **37 casos** (2 sem jogo capturado).

| Janela | Média | Mediana | IC95 | Caiu 1c ou mais |
|---|---|---|---|---|
| 60 min **antes** da notícia | **−2,1c** | −1,0c | [−3,8c; −0,8c] | 19 de 37 |
| 60 min **depois** da notícia | −0,4c | 0,0c | [−1,2c; +0,4c] | 14 de 37 |

**Exemplo:** Thunder em 21/11. Caruso, Williams e Topic aparecem como `Out` às 22:29 UTC. O
preço do Thunder caiu de 0,505 para 0,325 por volta das 22:15, uns 14 minutos **antes** da
ESPN, e não caiu mais depois.

**A conferência mostra por que o método por minuto é necessário.** Pelas capturas de hora em
hora, o preço "cai depois" (−2,5c, IC95 [−4,3c; −1,0c], n=25). Esse movimento é o mesmo que o
histórico por minuto põe antes da notícia: a janela de uma hora abraça a notícia.

**Leitura:** a lista da ESPN chega depois do mercado. Quem decide o preço já sabia, por
setorista, rede social do time ou relatório oficial. Para usar lesão como vantagem, a fonte
precisaria ser mais rápida que a ESPN, e isso é jogo de latência, não de modelo.

**Limitações:**
- Amostra de 5 dias.
- `espn_utc` é a hora da atualização na ESPN, não a da primeira notícia pública.
- O histórico por minuto é o preço médio da Polymarket, não o ask.
- Não separa a importância do jogador (titular × reserva).

Reproduzir: `python estudos/injury_lag.py` (requer `data/paper_log.csv` e
`data/injuries_log.csv` do coletor em papel; o histórico por minuto fica em cache em
`data/cache/injury_lag/`).
