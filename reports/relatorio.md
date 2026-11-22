# Modelo Elo x mercado da Polymarket (NBA)

Gerado em 2026-11-21 20:46 UTC. Modelo versão `cbad5d6dcd`, parâmetros {'k': 20.0, 'home': 40.0, 'b2b': 50.0, 'regress': 0.4} ajustados só em 2019-2024.
Preço de referência: último preço do histórico pelo menos 60 min antes do jogo. Jogos casados: 1463. Resultado da Polymarket diferente do placar: 0.
Mistura = logit com peso 0.00 no modelo (ajustado em 2025-26).

## Qualidade da probabilidade

| Recorte | Jogos | Log loss mercado | Log loss modelo | Log loss mistura | Brier mercado | Brier modelo | Modelo − mercado (log loss) |
|---|---|---|---|---|---|---|---|
| 2025-26 (validação) | 1233 | 0.5689 | 0.5954 | 0.5689 | 0.1942 | 0.2045 | +0.0265 (IC95 +0.0149 a +0.0375) |
| 2026-27 (teste, fora de tudo) | 230 | 0.5646 | 0.5965 | 0.5646 | 0.1921 | 0.2054 | +0.0319 (IC95 +0.0096 a +0.0550) |
| todos | 1463 | 0.5682 | 0.5956 | 0.5682 | 0.1939 | 0.2047 | +0.0274 (IC95 +0.0175 a +0.0376) |

Mistura − mercado no teste: +0.0000 (IC95 -0.0000 a +0.0000) (negativo = mistura melhor que o mercado).

## Apostas simuladas (1 unidade, taxa de taker + 0,5c de derrapagem)

Regra principal: apostar quando prob − custo ≥ 3%. As outras linhas são só sensibilidade, não escolha de limiar.

| Fonte | Recorte | Limiar | Apostas | ROI | Lucro (u) |
|---|---|---|---|---|---|
| modelo | 2025-26 (validação) | 3% **(principal)** | 767 | -14.8% (IC95 -24.3% a -4.5%) | -113.4 |
| modelo | 2025-26 (validação) | 0% | 1074 | -12.4% (IC95 -20.7% a -3.8%) | -132.7 |
| modelo | 2025-26 (validação) | 2% | 863 | -13.9% (IC95 -23.6% a -3.9%) | -119.9 |
| modelo | 2025-26 (validação) | 5% | 579 | -13.8% (IC95 -25.7% a -1.5%) | -79.7 |
| modelo | 2025-26 (validação) | 8% | 356 | -9.9% (IC95 -25.0% a +6.7%) | -35.2 |
| modelo | 2026-27 (teste, fora de tudo) | 3% **(principal)** | 135 | -32.3% (IC95 -50.3% a -13.0%) | -43.5 |
| modelo | 2026-27 (teste, fora de tudo) | 0% | 197 | -19.9% (IC95 -36.1% a -2.2%) | -39.2 |
| modelo | 2026-27 (teste, fora de tudo) | 2% | 155 | -27.7% (IC95 -45.3% a -10.5%) | -43.0 |
| modelo | 2026-27 (teste, fora de tudo) | 5% | 100 | -24.1% (IC95 -47.1% a +0.8%) | -24.1 |
| modelo | 2026-27 (teste, fora de tudo) | 8% | 54 | -18.3% (IC95 -51.5% a +17.8%) | -9.9 |
| modelo | todos | 3% **(principal)** | 902 | -17.4% (IC95 -26.1% a -8.4%) | -156.9 |
| modelo | todos | 0% | 1271 | -13.5% (IC95 -20.7% a -5.9%) | -171.9 |
| modelo | todos | 2% | 1018 | -16.0% (IC95 -24.6% a -7.1%) | -162.9 |
| modelo | todos | 5% | 679 | -15.3% (IC95 -26.1% a -4.4%) | -103.8 |
| modelo | todos | 8% | 410 | -11.0% (IC95 -25.5% a +3.7%) | -45.1 |

A mistura não aparece nas apostas: o melhor peso para o modelo foi 0, ou seja, ela é o próprio mercado e nunca vê vantagem.

## Calibração (todos os jogos)

| Faixa | Jogos (mercado) | Mercado previu | Aconteceu | Jogos (modelo) | Modelo previu | Aconteceu |
|---|---|---|---|---|---|---|
| 0%–10% | 24 | 7.7% | 0.0% | — | — | — |
| 10%–20% | 84 | 15.5% | 11.9% | 49 | 16.8% | 4.1% |
| 20%–30% | 115 | 24.9% | 24.3% | 123 | 25.7% | 25.2% |
| 30%–40% | 177 | 35.2% | 33.9% | 180 | 35.5% | 30.0% |
| 40%–50% | 205 | 44.8% | 47.3% | 223 | 45.2% | 45.7% |
| 50%–60% | 204 | 55.4% | 53.9% | 259 | 55.2% | 60.6% |
| 60%–70% | 217 | 64.9% | 65.0% | 262 | 64.8% | 62.6% |
| 70%–80% | 207 | 74.8% | 76.3% | 214 | 74.8% | 75.2% |
| 80%–90% | 184 | 84.9% | 81.5% | 134 | 84.3% | 85.8% |
| 90%–100% | 46 | 93.1% | 100.0% | 16 | 91.9% | 87.5% |
