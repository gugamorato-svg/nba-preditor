# nba-preditor

[English](README.md) · **Português**

Preditor de vitória na NBA (Elo) comparado ao preço da Polymarket, para testar,
**só no papel**, se existe vantagem antes de pensar em dinheiro. O projeto lê
apenas dados públicos e não envia ordens nem usa carteira ou chave.

Usa só a biblioteca padrão do Python (3.12+). Para os testes, precisa do `pytest`.

## Resultado até agora

O mercado ganha. Nos 1.463 jogos da temporada regular com preço da Polymarket
(2025-26 e o começo de 2026-27):

- a log loss do modelo é pior: 0,596 contra 0,568 do mercado, com o IC95 da
  diferença todo acima de zero;
- o peso ótimo do modelo numa mistura com o mercado é 0;
- a regra de apostas simuladas perde 17% (IC95 −26% a −8%) em 902 apostas.

Detalhes em [`reports/relatorio.md`](reports/relatorio.md). Teorias testadas
ficam em [`estudos/`](estudos/). A do jetlag, por exemplo, não passou.

## Como usar

```powershell
python fetch_results.py      # calendário e placares desde 2018-19 (fixturedownload.com)
python fetch_polymarket.py   # preço 1h antes de cada jogo encerrado na Polymarket (~20 min)
python model.py --fit        # ajusta o Elo SÓ em 2019-2024 (opcional: já vem salvo)
python evaluate.py           # modelo x mercado -> reports/relatorio.md
python paper_collect.py      # captura em papel dos próximos jogos (rodar de hora em hora)
python evaluate.py --paper   # placar do teste prospectivo
python -m pytest
```

No Windows, `run_paper.cmd` serve para o Agendador de Tarefas. Ele usa o Python
da variável `NBA_PYTHON`, se existir.

## O que tem dentro

| Arquivo | Para quê |
|---|---|
| `fetch_results.py` | Baixa os CSVs da temporada regular e grava `data/games.csv` |
| `fetch_polymarket.py` | Lista os jogos da série NBA na Polymarket e pega o preço do mandante 60 min antes, gravando `data/market.csv` |
| `model.py` | Elo com mando, margem de vitória, regressão entre temporadas e penalidade de back-to-back, previsto jogo a jogo só com o passado |
| `evaluate.py` | Log loss, Brier, calibração e ROI simulado com taxa de taker e IC95 por bootstrap |
| `paper_collect.py` | Acrescenta previsão + bid/ask do livro em `data/paper_log.csv` e chama `injuries.py` |
| `injuries.py` | Guarda em `data/injuries_log.csv` só as mudanças na lista de lesões da ESPN |
| `estudos/` | Teorias testadas com pré-registro |
| `PROTOCOLO.md` | Regras do teste em papel, fixadas antes de começar |

Os dados (`data/*.csv`) não ficam no repositório: os scripts baixam tudo de novo.

## Cuidados

- **Sem vazamento:** cada previsão usa só jogos anteriores. Há um teste que muda
  o placar de um jogo e confere que a previsão dele não muda.
- **Comparar com o mercado, não com o acerto:** acertar 66% na NBA é o normal de
  quem escolhe o favorito.
- **Log loss melhor não é lucro**, e menos de ~500 apostas é ruído.
- **Taxa:** a Polymarket cobra taker `0,05 × p × (1 − p)` por share nos jogos da NBA.

## Limitações

- Só temporada regular: playoffs e play-in ficam de fora.
- O preço histórico fica perto do meio do livro, não é o ask. O backtest cobra
  0,5 centavo a mais, e o teste em papel usa o ask de verdade.
- O modelo não sabe de lesões nem de descanso planejado. O mercado sabe.

Verifique se mercados de previsão são permitidos onde você mora. Isto é um
estudo, não recomendação de aposta.
