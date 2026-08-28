# LeaderV10 Roadmap (SOTA AI & GA)

Este documento registra o planejamento em etapas (sprints) para a implementação da décima geração do agente (LeaderV10). Devido à complexidade de implementar lógicas anti-monopólio, especulação de mercado e treinamento evolutivo (Optuna), o desenvolvimento foi dividido em iterações curtas e verificáveis.

## Sprint 1: LeaderV10.0 (Baseline Parametrizada) - [CONCLUÍDO]
**Objetivo:** Isolar números mágicos e preparar a arquitetura para o algoritmo evolutivo sem alterar comportamento.
- [x] Extrair parâmetros hardcoded (dias de fechamento, buffers de caixa, limiares de compras, multiplicadores de ROI) para uma dataclass `V10Config`.
- [x] Criar `LeaderV10Engine` herdando comportamento base e aceitando o config injetado.
- [x] Adicionar `optuna` às dependências locais (`uv add --group competition optuna`).
- [x] Validar que os testes unitários garantem retrocompatibilidade total de comportamento com a V9.

## Sprint 2: LeaderV10.1 (Market Speculation) - [CONCLUÍDO]
**Objetivo:** Permitir retenção de inventário contra quedas bruscas de preço.
- [x] Adicionar `speculation_hold_threshold` e `speculation_min_liquidity` ao `V10Config`.
- [x] Atualizar o módulo `_sales` na engine.
- [x] Lógica: Se o preço de um crop cair abaixo do limite e houver caixa para segurar a operação, reter no inventário.
- [x] Escrever teste unitário para garantir que crops valiosos não sejam vendidos em baixa.

## Sprint 3: LeaderV10.2 (Opponent-Aware Anti-Monopólio) - [TODO]
**Objetivo:** Desviar a atenção de safras dominadas pelo adversário, evitando colapso mutuo de preços.
- [ ] Adicionar `opponent_crop_penalty` ao `V10Config`.
- [ ] Modificar `_dynamic_crop_portfolio` para iterar sobre as plantas no tabuleiro do oponente (`state.opponent_tiles`).
- [ ] Aplicar penalidade de ROI para colheitas nas quais o inimigo tem um monopólio visível.
- [ ] Escrever testes garantindo o pivô automático (ex: trocar Melão por Morango se o oponente plantar Melão).

## Sprint 4: LeaderV10.3 (Treinamento Genético / CMA-ES) - [TODO]
**Objetivo:** Deixar a máquina descobrir matematicamente a combinação perfeita para todos os parâmetros.
- [ ] Criar o script `scripts/optimize_v10.py`.
- [ ] Implementar a função objetivo do `Optuna` rodando N simulações locais (V10 vs V9).
- [ ] Utilizar Algoritmos Genéticos (CMA-ES/TPE) para descobrir os pesos ideais.
- [ ] Integrar no `Makefile` (ex: `make optimize-v10`).
- [ ] Alimentar os resultados da otimização de volta para os valores *default* do `V10Config` antes de submeter ao Kaggle.

