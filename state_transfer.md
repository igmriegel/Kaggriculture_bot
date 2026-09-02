# State Transfer: Kaggriculture Bot Development (V11 Hybrid Engine)

Este documento serve como um dump completo e detalhado do estado atual do desenvolvimento da **Leader V11 (Hybrid Engine)**.

---

## 📌 Status Atual do Projeto

Desenvolvemos e consolidamos a **Leader V11 (Hybrid Engine)** em [`LeaderV11Engine`](file:///home/igor/Documentos/heuristics/Kaggriculture_bot/agent/engines/leader_v11.py), uma engine híbrida avançada que une:
1. **Monte Carlo Price Oracle (`agent/domain/monte_carlo.py`):** Projeção de mercado analítica closed-form $O(1)$ (< 0.5ms) para simular distribuições de preços sob incerteza de futuros shops.
2. **Online Opponent Behavioral Tracker (`agent/domain/opponent_model.py`):** Rastreamento de padrões de plantio, colheita e liquidez do oponente.
3. **Mecânica de Viabilidade Dinâmica de Mercado:** Eliminamos 100% dos cutoffs estáticos de dia. Melão e Morango agora são regulados exclusivamente por maturação física exata ($\text{dia} + \text{maturação} \le 30$) e pela projeção de demanda do Monte Carlo no dia da colheita.
4. **Otimização Evolutiva (Optuna + CMA-ES em `scripts/optimize_v11.py`):** Varrida do espaço de busca dos 6 parâmetros essenciais.
5. **Algoritmo Húngaro em Scipy (`agent/engines/spatial_planner.py`):** Substituição da busca combinatória por `scipy.optimize.linear_sum_assignment` ($O(N^3)$).

---

## 📊 Resultados do Último Benchmark (N=30 per matchup)

| Oponente | Win Rate | Avg V11 | Avg Opp | Min V11 | Max V11 | Min Opp | Max Opp | Margin | Set Time |
|:---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **LEADER-V7** | **86.7%** | $68,352.93 | $50,040.17 | $37,673 | $87,987 | $24,305 | $87,107 | **+$18,312.77** | 97.8s |
| **LEADER-V8** | **93.3%** | $64,834.33 | $51,497.53 | $36,357 | $89,398 | $25,016 | $76,416 | **+$13,336.80** | 119.0s |
| **LEADER-V9** | **63.3%** | $61,959.67 | $59,080.03 | $26,669 | $87,131 | $26,162 | $90,972 | **+$2,879.63** | 88.4s |
| **LEADER-V9-1** | **70.0%** | $61,499.40 | $59,258.93 | $28,761 | $78,009 | $28,964 | $81,655 | **+$2,240.47** | 89.2s |

*Obs: A V11 mantêm **margem líquida positiva e superior em 100% dos confrontos**, com a Win Rate contra V9-1 subindo de 58% para **70%**.*

---

## 💻 Instruções de Execução

1. **Testes Unitários:**
   ```bash
   uv run pytest
   ```
2. **Benchmark Paralelo:**
   ```bash
   make benchmarks N=30
   ```
3. **Otimizador Optuna:**
   ```bash
   uv run python scripts/optimize_v11.py -t 40 -s 6
   ```
