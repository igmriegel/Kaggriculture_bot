# MEGA AUDITORIA E PLANO DE EVOLUÇÃO — KAGGRICULTURE HEURISTIC ENGINE

Você é o **Lead Researcher, Game Theorist, Competitive AI Engineer e Benchmark Analyst** responsável por conduzir uma revisão profunda da minha engine heurística para a competição **Kaggriculture do Kaggle**.

Estamos desenvolvendo uma IA baseada em heurísticas para jogar Kaggriculture. O objetivo não é apenas melhorar alguns números de benchmark, mas construir uma engine **forte, robusta, adaptativa, estrategicamente coerente e capaz de competir contra diferentes estilos de oponentes**.

## OBJETIVO PRINCIPAL

Quero evoluir a engine até atingir **pelo menos 90% de win rate contra TODAS as engines de referência nos benchmarks**, antes de realizar uma nova submissão ao Kaggle.

O benchmark atual é:

```text
=== BENCHMARKS DONE ===
Results written to reports/benchmarks/latest.json and reports/benchmarks/latest.md

=== SUMMARY TABLE ===
Matchup            Win Rate   Avg V9.1    Avg Opp   Min V9.1   Max V9.1    Min Opp    Max Opp     Margin
--------------------------------------------------------------------------------------------------------
V9.1 vs LEADER-V6       97.0% $   65,597 $   51,444 $   35,166 $   92,553 $   23,000 $   76,230    +14,153
V9.1 vs LEADER-V7       97.0% $   63,890 $   45,399 $   22,580 $   87,760 $   22,776 $   72,961    +18,491
V9.1 vs LEADER-V8       93.0% $   65,078 $   53,694 $   30,580 $   89,403 $   24,339 $   83,697    +11,384
V9.1 vs LEADER-V9       57.0% $   60,341 $   59,142 $   23,377 $   87,945 $   26,106 $   86,132     +1,199
V9.1 vs LEADER-V10     100.0% $   69,320 $    8,334 $   30,487 $   97,068 $    2,133 $   30,707    +60,986
```

O problema crítico é claramente:

**V9.1 vs LEADER-V9 → apenas 57% de vitórias.**

As outras engines já estão acima do objetivo de 90%.

Portanto, a investigação deve dar **prioridade máxima às derrotas contra LEADER-V9**, mas sem assumir antecipadamente que a solução é simplesmente adaptar a engine especificamente contra V9.

---

# 1. PRIMEIRO: ENTENDA COMPLETAMENTE O PROJETO

Antes de propor qualquer alteração:

1. Explore toda a estrutura do projeto.
2. Leia a documentação disponível.
3. Identifique:
   - regras do jogo;
   - estado do jogo;
   - ações disponíveis;
   - economia;
   - sistema de plantio;
   - sistema de colheita;
   - preços;
   - demanda;
   - expansão da cidade;
   - upgrades;
   - limitações;
   - condições de vitória;
   - horizonte temporal;
   - aleatoriedade;
   - mecanismos de risco/recompensa.
4. Mapeie completamente a arquitetura da engine V9.1.
5. Identifique todas as heurísticas existentes.
6. Identifique pesos, thresholds, prioridades e regras de decisão.
7. Identifique onde a engine toma decisões:
   - o que plantar;
   - quando plantar;
   - quanto plantar;
   - quando colher;
   - o que vender;
   - quando vender;
   - quando guardar estoque;
   - como reagir aos preços;
   - como reagir à expansão da cidade;
   - como reagir ao comportamento do adversário;
   - como administrar dinheiro;
   - como administrar risco;
   - como decidir investimentos;
   - como decidir entre ganho imediato e crescimento futuro.

**Não proponha mudanças antes de entender o sistema.**

---

# 2. AUDITE OS BENCHMARKS EM PROFUNDIDADE

Não se limite à tabela agregada.

Localize e analise:

- `reports/benchmarks/latest.json`
- `reports/benchmarks/latest.md`
- logs de partidas;
- replays;
- estados por turno;
- decisões tomadas;
- resultados financeiros;
- ações do jogador;
- ações dos adversários;
- qualquer outro artefato de benchmark disponível.

Se houver centenas de partidas, faça análise estatística e agrupamentos em vez de tentar analisar tudo manualmente.

Quero descobrir:

### A. Quando perdemos?

Determine:

- em quais turnos as derrotas começam a se tornar prováveis;
- qual era o estado da partida naquele momento;
- qual decisão mudou a trajetória da partida;
- se a derrota foi gradual ou causada por um erro crítico;
- se existiam sinais antecipados de derrota;
- se a engine percebeu esses sinais;
- se havia uma ação alternativa claramente melhor.

### B. Por que perdemos?

Classifique as derrotas em categorias.

Exemplos:

- má seleção de cultura;
- timing ruim de plantio;
- excesso de estoque;
- falta de estoque;
- venda prematura;
- venda tardia;
- baixa utilização de capital;
- investimento errado;
- expansão ignorada;
- reação tardia à expansão;
- previsão ruim de demanda;
- exploração insuficiente de oportunidades;
- estratégia excessivamente gananciosa;
- estratégia excessivamente conservadora;
- incapacidade de reagir ao adversário;
- horizonte de planejamento curto;
- problema de timing;
- problema de risco;
- heurística conflitante;
- threshold inadequado;
- decisão localmente ótima mas globalmente ruim;
- ausência de estratégia de recuperação após ficar atrás;
- comportamento repetitivo/previsível;
- exploração insuficiente;
- exploração excessiva;
- outro.

Não assuma essas categorias como verdade.

Crie categorias baseadas nos dados encontrados.

---

# 3. FAÇA UMA ANÁLISE ESPECÍFICA DO LEADER-V9

O LEADER-V9 é atualmente nosso principal problema.

Quero descobrir:

### O que V9 faz que nossas outras engines adversárias não fazem?

Compare V9 com:

- LEADER-V6
- LEADER-V7
- LEADER-V8
- LEADER-V10

Identifique diferenças comportamentais.

Investigue:

- padrão de plantio;
- composição das culturas;
- timing;
- agressividade;
- gestão de caixa;
- estoque;
- venda;
- reação à cidade;
- reação aos preços;
- reação ao nosso comportamento;
- utilização de oportunidades;
- estratégia no início;
- estratégia no meio;
- estratégia no final.

Determine se V9 possui algum comportamento que explora especificamente uma fraqueza estrutural da V9.1.

---

# 4. NÃO CONFUNDA CORRELAÇÃO COM CAUSALIDADE

Para cada hipótese encontrada, procure evidências.

Não diga simplesmente:

> "Perdemos porque plantamos X."

Investigue:

- X realmente causou a derrota?
- ou jogadores que estavam em uma situação ruim já tendiam a plantar X?
- X foi uma causa ou consequência?
- existia uma ação alternativa?
- quantas vezes esse padrão ocorreu?
- qual é a taxa de vitória quando fazemos X?
- qual é a taxa de vitória quando não fazemos X?
- o efeito depende do estado do jogo?
- o efeito depende do turno?
- o efeito depende da economia?
- o efeito depende do comportamento do adversário?

Sempre que possível, transforme hipóteses em testes mensuráveis.

---

# 5. IDENTIFIQUE "DECISION POINTS" CRÍTICOS

Quero que você descubra os momentos em que a engine tinha uma escolha importante.

Para cada decisão crítica, registre conceitualmente:

```text
Estado do jogo
↓
Opções disponíveis
↓
Decisão tomada pela V9.1
↓
Consequência imediata
↓
Consequência futura
↓
Resultado final
↓
Alternativa potencialmente superior
```

Procure especialmente por:

- decisões irreversíveis;
- decisões que comprometem vários turnos;
- decisões de alto impacto econômico;
- decisões próximas de mudanças de mercado;
- decisões antes/depois da expansão da cidade;
- decisões em que o adversário mudou de estratégia;
- decisões em que estávamos na frente;
- decisões em que estávamos atrás.

---

# 6. ANALISE A ECONOMIA COMO UM SISTEMA DINÂMICO

Não analise apenas dinheiro final.

Investigue:

- crescimento do capital;
- velocidade de geração de receita;
- retorno sobre investimento;
- utilização do capital;
- capital parado;
- estoque;
- valor esperado do estoque;
- custo de oportunidade;
- timing de vendas;
- volatilidade;
- risco de ficar sem liquidez;
- crescimento composto;
- investimentos de curto vs longo prazo.

Quero descobrir:

> Qual comportamento econômico maximiza a probabilidade de vitória, e não simplesmente o dinheiro em um turno específico?

---

# 7. ANALISE PLANTIO COMO UMA DECISÃO ESTRATÉGICA

Não trate "qual cultura plantar" como uma simples tabela de rentabilidade.

Investigue:

- lucro esperado;
- variância;
- liquidez;
- tempo até retorno;
- demanda;
- competição;
- saturação;
- sinergias;
- complementaridade;
- risco;
- oportunidade futura;
- expansão da cidade;
- comportamento esperado do adversário.

Quero saber se nossa engine deveria utilizar algo mais próximo de:

```text
Expected Value
+
Risk
+
Opportunity Cost
+
Future Value
+
Opponent Interaction
+
City Expansion Impact
```

em vez de simplesmente:

```text
Expected Profit
```

---

# 8. ANALISE A EXPANSÃO DA CIDADE

Faça uma investigação específica sobre os eventos de expansão.

Descubra:

- como a expansão altera a economia;
- quais culturas ficam mais interessantes;
- quais deixam de ser interessantes;
- como a demanda muda;
- quanto tempo leva para capturar a oportunidade;
- se a V9.1 reage cedo ou tarde;
- se existe um período crítico antes/depois da expansão;
- se devemos antecipar a expansão;
- se devemos guardar recursos antes dela;
- se devemos alterar estoque;
- se devemos alterar composição de plantio.

Determine se existe uma estratégia geral de:

**"preparação → evento → exploração → normalização"**

para expansões.

---

# 9. INVESTIGUE HORIZONTE DE PLANEJAMENTO

Uma possível fraqueza de engines heurísticas é otimizar a ação atual sem considerar suficientemente os próximos turnos.

Teste conceitualmente se temos problemas de:

- myopia;
- greedy optimization;
- ausência de lookahead;
- decisões conflitantes entre curto e longo prazo.

Procure situações em que:

```text
Decisão A:
+100 agora
-500 depois

Decisão B:
+20 agora
+700 depois
```

e determine se nossa heurística consegue identificar B.

Se não consegue, proponha mecanismos de lookahead compatíveis com a arquitetura atual.

---

# 10. ANALISE ADAPTAÇÃO AO ADVERSÁRIO

Determine se a V9.1 é:

- reativa;
- parcialmente adaptativa;
- ou essencialmente estática.

Investigue se conseguimos inferir:

- estratégia do adversário;
- intenção;
- agressividade;
- preferência de culturas;
- timing;
- apetite por risco;
- comportamento de venda;
- reação à cidade.

Quero avaliar se devemos introduzir uma camada de:

**Opponent Modeling**

sem transformar a engine em algo excessivamente complexo.

---

# 11. PROCURE POR HEURÍSTICAS CONFLITANTES

Audite a lógica procurando situações como:

```text
Heurística A diz: faça X
Heurística B diz: faça Y
Heurística C diz: espere
```

Identifique:

- conflitos;
- prioridades implícitas;
- regras que se anulam;
- thresholds redundantes;
- thresholds muito rígidos;
- heurísticas que funcionam em determinados estados mas falham em outros.

Pergunte:

> Existe uma arquitetura de decisão melhor do que simplesmente acumular mais regras?

---

# 12. PROCURE PADRÕES NAS VITÓRIAS

Não analise apenas as derrotas.

Compare partidas vencedoras e perdedoras.

Descubra:

- comportamentos associados a vitórias;
- decisões recorrentes;
- sequência de ações;
- timing;
- composição de culturas;
- caixa;
- estoque;
- reação à cidade;
- comportamento contra adversários agressivos/passivos.

Quero encontrar **invariantes estratégicos**.

Exemplo:

> "Independentemente do adversário, quando X acontece, engines vencedoras tendem a fazer Y."

Esses padrões são muito mais valiosos do que regras específicas para LEADER-V9.

---

# 13. PROCURE PADRÕES DE "WINNING TRAJECTORY"

Tente identificar uma trajetória típica de vitória.

Por exemplo:

```text
Early Game
↓
Acumulação de capital
↓
Primeira oportunidade
↓
Expansão
↓
Mudança de composição
↓
Aceleração
↓
Domínio econômico
```

Determine se existe uma sequência estratégica recorrente.

Também procure trajetórias de derrota:

```text
Early Game
↓
Pequena decisão ruim
↓
Perda de oportunidade
↓
Capital insuficiente
↓
Atraso
↓
Decisões defensivas
↓
Snowball
↓
Derrota
```

---

# 14. IDENTIFIQUE SNOWBALLS E PONTOS DE NÃO RETORNO

Determine:

- quando uma vantagem se torna difícil de recuperar;
- quando uma desvantagem ainda é reversível;
- quais recursos criam snowball;
- quais decisões aceleram o snowball;
- se nossa engine reconhece esses estados.

Crie, se possível, conceitos como:

```text
Winning Position
Neutral Position
Danger Position
Critical Position
Recovery Position
```

e avalie se a política da engine deveria mudar dependendo desses estados.

---

# 15. CRIE UMA MATRIZ DE ESTADOS ESTRATÉGICOS

Proponha uma classificação do estado atual do jogo.

Por exemplo:

| Estado | Objetivo |
|---|---|
| Muito à frente | Maximizar vantagem / reduzir risco |
| À frente | Crescer mantendo segurança |
| Equilibrado | Explorar oportunidades |
| Levemente atrás | Aumentar upside |
| Muito atrás | Estratégia de recuperação |
| Evento iminente | Preparação |
| Pós-evento | Exploração |

Não copie essa tabela cegamente.

Crie uma versão baseada na dinâmica real do jogo.

---

# 16. TESTE A ROBUSTEZ DAS MELHORIAS

Uma melhoria só deve ser considerada boa se:

1. aumentar significativamente a performance contra LEADER-V9;
2. não destruir a performance contra V6/V7/V8;
3. não depender excessivamente de um comportamento específico do V9;
4. fizer sentido estratégico;
5. reduzir fragilidades gerais.

Quero evitar:

**overfitting ao benchmark.**

Sempre pergunte:

> "Essa mudança melhora a estratégia da engine ou apenas explora uma peculiaridade desse adversário?"

---

# 17. FAÇA ANÁLISE DE SENSIBILIDADE

Identifique parâmetros críticos da engine:

- thresholds;
- pesos;
- margens;
- fatores de risco;
- horizonte temporal;
- prioridades;
- pesos de culturas;
- thresholds de venda;
- thresholds de estoque;
- thresholds de investimento.

Para cada parâmetro importante, determine:

- valor atual;
- comportamento esperado;
- possíveis alternativas;
- impacto esperado;
- risco de regressão.

Se possível, proponha experimentos sistemáticos em vez de alterar parâmetros manualmente de forma arbitrária.

---

# 18. CRIE UMA MATRIZ DE EXPERIMENTOS

Não quero uma lista vaga de ideias.

Quero experimentos concretos.

Para cada experimento:

```text
ID
Hipótese
Problema que pretende resolver
Alteração proposta
Arquivos/módulos afetados
Parâmetros envolvidos
Benchmark necessário
Métrica principal
Métricas secundárias
Resultado esperado
Risco
Critério de sucesso
Critério de rollback
```

Priorize os experimentos por:

```text
Impacto esperado
×
Confiança na hipótese
×
Facilidade de implementação
×
Generalização
```

---

# 19. DEFINA O PLANO DE DESENVOLVIMENTO

Ao final da investigação, construa um roadmap.

Organize em:

### P0 — Correções críticas

Problemas que provavelmente explicam diretamente as derrotas.

### P1 — Melhorias estratégicas

Mudanças capazes de melhorar significativamente a engine.

### P2 — Robustez

Mudanças que aumentam consistência e reduzem variância.

### P3 — Exploração

Ideias de maior risco ou maior complexidade.

Para cada item, explique:

- problema;
- evidência;
- solução;
- impacto esperado;
- complexidade;
- risco;
- prioridade.

---

# 20. DEFINA CRITÉRIOS DE SUCESSO

Nossa meta mínima é:

```text
V9.1 vs LEADER-V6  >= 90%
V9.1 vs LEADER-V7  >= 90%
V9.1 vs LEADER-V8  >= 90%
V9.1 vs LEADER-V9  >= 90%
V9.1 vs LEADER-V10 >= 90%
```

Mas não quero otimizar apenas para a média.

Também avalie:

- win rate;
- margem média;
- margem mediana;
- distribuição dos resultados;
- pior resultado;
- variância;
- consistência;
- taxa de recuperação;
- desempenho em partidas difíceis.

Se possível, estabeleça um **score composto de robustez**.

---

# 21. CRIE UM "FAILURE TAXONOMY"

Ao terminar a análise, produza uma taxonomia das falhas da V9.1.

Exemplo:

```text
FAILURE
├── Economy
│   ├── Liquidity
│   ├── Inventory
│   └── Investment
│
├── Farming
│   ├── Crop Selection
│   ├── Timing
│   └── Allocation
│
├── Market
│   ├── Selling
│   ├── Demand
│   └── Price
│
├── Strategy
│   ├── Planning Horizon
│   ├── Risk
│   └── Opportunity Cost
│
├── Opponent
│   ├── Prediction
│   ├── Adaptation
│   └── Exploitation
│
└── City
    ├── Expansion Preparation
    ├── Expansion Reaction
    └── Post Expansion
```

A taxonomia final deve ser baseada nos dados encontrados no projeto.

---

# 22. CRIE UM "WINNING PLAYBOOK"

Depois da auditoria, produza um playbook estratégico da engine.

Quero algo semelhante a:

```text
WHEN X:
    prefer Y

WHEN A AND B:
    avoid C

WHEN CITY EXPANSION IS APPROACHING:
    prepare D

WHEN AHEAD:
    reduce risk

WHEN BEHIND:
    increase upside

WHEN OPPONENT DOES X:
    respond with Y
```

Mas essas regras devem surgir da análise, e não ser inventadas antecipadamente.

---

# 23. IDENTIFIQUE O QUE NÃO DEVEMOS FAZER

Crie uma seção:

## "ANTI-PATTERNS"

Liste comportamentos que a engine deveria evitar.

Por exemplo:

- vender cedo demais;
- plantar por lucro nominal sem considerar demanda;
- acumular estoque sem saída;
- perseguir uma oportunidade já perdida;
- ignorar expansão;
- assumir que o mercado permanecerá estável;
- usar a mesma estratégia independentemente do estado;
- otimizar uma decisão isolada.

Novamente: só inclua padrões comprovados pela análise.

---

# 24. PRODUZA UMA ANÁLISE DE "REGRET"

Para decisões críticas nas partidas perdidas, tente estimar:

> Quanto valor perdemos por ter escolhido a ação tomada em vez da melhor alternativa plausível?

Crie uma análise de regret para descobrir quais tipos de decisão possuem maior custo.

Isso deve ajudar a priorizar o desenvolvimento.

---

# 25. NÃO FAÇA ALTERAÇÕES IMEDIATAMENTE

Nesta etapa, **não altere o código automaticamente**.

Primeiro entregue um plano de investigação e desenvolvimento.

A sequência obrigatória é:

```text
AUDIT
↓
EVIDENCE
↓
HYPOTHESES
↓
ROOT CAUSES
↓
EXPERIMENTS
↓
PRIORITIZATION
↓
IMPLEMENTATION PLAN
↓
BENCHMARK PLAN
```

Somente depois que o plano estiver suficientemente fundamentado deveremos partir para implementação.

---

# FORMATO OBRIGATÓRIO DO RELATÓRIO FINAL

Estruture o resultado exatamente nestas grandes seções:

## 1. Executive Summary

Resumo das principais descobertas.

## 2. Current State

Avaliação da V9.1 atualmente.

## 3. Benchmark Analysis

Análise completa dos benchmarks.

## 4. LEADER-V9 Deep Dive

Investigação profunda das derrotas contra V9.

## 5. Loss Root Causes

Principais causas das derrotas.

## 6. Winning Patterns

Padrões associados às vitórias.

## 7. Strategic Weaknesses

Fraquezas estruturais da engine.

## 8. Heuristic Audit

Auditoria das heurísticas atuais.

## 9. Economic Analysis

Análise econômica.

## 10. Farming Strategy Analysis

Análise das decisões de plantio.

## 11. Market Analysis

Análise de vendas, demanda e preços.

## 12. City Expansion Analysis

Análise da expansão da cidade.

## 13. Opponent Modeling

Avaliação da capacidade de adaptação ao adversário.

## 14. Planning Horizon

Avaliação de lookahead e decisões de curto/longo prazo.

## 15. Failure Taxonomy

Taxonomia das falhas.

## 16. Winning Playbook

Princípios estratégicos encontrados.

## 17. Anti-Patterns

Comportamentos que devemos evitar.

## 18. Experiment Matrix

Experimentos propostos.

## 19. Prioritized Roadmap

Roadmap P0/P1/P2/P3.

## 20. Benchmark Strategy

Como devemos testar cada alteração.

## 21. Success Criteria

Critérios objetivos para considerar a V9.1 pronta.

## 22. Risks & Overfitting

Riscos de overfitting aos benchmarks atuais.

## 23. Recommended Next Sprint

Defina exatamente o que deve ser implementado primeiro.

---

# PRINCÍPIO FUNDAMENTAL

Não quero simplesmente uma engine que tenha:

> "90% contra os cinco adversários atuais."

Quero uma engine que tenha aprendido **os princípios estratégicos do jogo**.

O objetivo é descobrir:

> **O que uma engine realmente forte precisa entender sobre Kaggriculture para vencer consistentemente?**

Sempre prefira:

**generalização > exploração de adversário específico**

**evidência > opinião**

**causa raiz > sintoma**

**experimento > tentativa aleatória**

**estratégia > coleção de regras**

**robustez > win rate isolado**

**qualidade da decisão > resultado de uma partida individual**

---

# REGRA FINAL

Se durante a investigação você encontrar uma hipótese interessante, **não a trate como fato**.

Classifique-a como:

- Confirmada
- Fortemente suportada
- Provável
- Incerta
- Refutada

E explique quais evidências sustentam essa classificação.

Se os dados disponíveis não forem suficientes para responder alguma pergunta, diga explicitamente:

> **"INSUFFICIENT EVIDENCE"**

e proponha qual experimento ou dado adicional seria necessário para responder.

Não invente evidências.

O resultado esperado deste trabalho é um **plano técnico e estratégico de evolução da V9.1**, fundamentado nos benchmarks e nos gameplays reais, que nos permita chegar a uma engine significativamente mais forte antes da próxima submissão ao Kaggle.