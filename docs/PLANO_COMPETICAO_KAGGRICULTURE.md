# Plano de competição — Kaggriculture

**Status:** em revisão antes da implementação  
**Data de referência:** 18 de agosto de 2026  
**Prazo-alvo:** 30 de setembro de 2026  
**Escopo desta versão:** planejamento e documentação; não é evidência de que o agente esteja implementado.

## 1. Objetivo e estratégia

Construir uma submissão competitiva, robusta e reproduzível para Kaggriculture,
priorizando uma primeira versão estável e precoce. A estratégia será evolutiva:

1. baseline seguro e observável;
2. heurística econômica;
3. RL de alto nível, se os dados e o tempo justificarem;
4. híbrida somente se demonstrar ganho consistente.

A métrica principal será **win rate**. Serão acompanhadas como métricas auxiliares:
lucro médio, variância, erros, ações inválidas, tempo de execução, perdas de
plantas/animais e estoque descartado.

As restrições a confirmar nas regras oficiais incluem tempo por turno, memória,
tamanho do pacote, dependências permitidas, acesso à internet, formato de
`main.py`, número de submissões ativas e duração exata da partida. A aceitação
manual das regras da competição é uma dependência explícita do projeto.

## 2. Estado atual e premissas

- O repositório foi considerado inicialmente vazio.
- Não há agente implementado nesta etapa de revisão.
- Dependências e ambiente local ainda precisam ser definidos e instalados.
- As regras da competição precisam ser aceitas manualmente.
- Não há dataset de treinamento inicial.
- O schema oficial das observações e ações deve ser tratado como fonte de verdade.
- Nomes de ações, economia, mapa e horizonte de 720 turnos são premissas a validar.

## 3. Escopo e não escopo

### Incluído

- agente submetível com fallback seguro;
- modelo normalizado de estado;
- planner, executor e políticas de mercado;
- runner local e métricas reproduzíveis;
- comparação heurística/RL/híbrida sob as mesmas sementes;
- empacotamento e teste sem caminhos locais.

### Não incluído nesta fase de documentação

- código de produção;
- treinamento de modelos;
- coleta real de episódios;
- submissão à competição;
- afirmações de desempenho sem benchmark.

## 4. Arquitetura planejada

```text
main.py
agent/
  engines/       # base, heuristic, rl, hybrid
  state/         # tracker, features
  planning/      # task_planner, executor, routes
  market/        # model, policy
  evaluation/    # runner, metrics, scenarios
  models/        # somente artefatos aprovados para submissão
docs/
```

Todas as engines deverão compartilhar:

```python
class Engine:
    def act(self, obs: dict) -> dict:
        ...
```

`main.py` poderá selecionar uma engine durante o desenvolvimento. A submissão
deverá carregar uma única engine estável, sem treinamento, notebook, dataset ou
dependência de caminho da máquina local.

## 5. Fases e critérios de aceite

### Fase 0 — Preparação

**F0.1 Estrutura:** diretórios importáveis, comandos documentados e caminhos portáveis.  
**F0.2 Ambiente:** versão mínima de Python, dependências fixadas, `kaggle_environments`
instalado e partida mínima local.  
**F0.3 Agente mínimo:** aceita observação válida, retorna ação válida, usa `PASS`
como fallback e completa partida contra `random` e contra si próprio.  
**F0.4 Runner:** suporta engine, oponente, sementes, episódios, logs opcionais e
comparação.

### Fase 1 — Observabilidade e estado

Normalizar dia, hora, jogador, caixa, posições, tiles, desbloqueios, plantas,
animais, shed, sementes, inventário, preços e lojas. O tracker calculará idade,
rega, plantio, produção, alimentação, colheita e dias restantes. O modelo
econômico estimará receita, custos, retorno por tile/dia, mão de obra, fertilizante
e risco de overflow. Métricas registrarão caixa final, resultado, erros, perdas,
estoque, fertilizante, terra, mãos e vendas por produto.

**Aceite:** observações de todos os turnos são normalizadas sem exceção e há
testes para plantas e animais em ciclos distintos.

### Fase 2 — Executor operacional

Mapear células, weeds, estruturas, shed e rotas; priorizar áreas desbloqueadas;
representar tarefas de mover, plantar, regar, fertilizar, colher, alimentar,
cuidar, construir, comprar, vender, transportar e contratar.

O executor deve revalidar a tarefa, recalcular rota, evitar conflitos, limitar
ordens de mercado e retornar `PASS` quando não houver ação segura.

**Aceite:** falhas de tile bloqueado, falta de dinheiro/insumos, shed cheio,
planta já regada, animal já alimentado e posição inesperada não causam erro fatal.

### Fase 3 — Heurística

Definir abertura, reserva de caixa, primeira mão, expansão, culturas, animais,
fertilizante e mercado. Cada decisão econômica deve considerar preço, demanda,
tempo restante, capacidade, custo de oportunidade e impacto da venda no preço.

**Benchmark mínimo:** 100 partidas contra `pass`, `random`, `starter` e a própria
heurística, com múltiplas sementes. Promoção exige erro próximo de zero,
estabilidade e melhoria mensurável sobre `starter`.

### Fase 4 — Dataset e ambiente RL

Coletar episódios da heurística, `random`, `starter` e versões anteriores. O RL
atuará em passos estratégicos, preferencialmente no início do dia, escolhendo mix
de culturas, animais, mãos, expansão, venda, fertilizante e reserva de caixa.
O executor continuará responsável pelas ações turno a turno.

Aplicar máscaras para dinheiro, espaço e tempo. A observação agregada deverá
conter ocupação, produção futura, caixa, preços, estoque, capacidade, lojas,
tempo restante e estimativa do adversário.

### Fase 5 — RL

Treinar progressivamente contra `pass`, `random`, `starter`, heurística
conservadora e agressiva. Variar sementes, lojas, preços, custos, duração e
adversários. Usar snapshots em self-play e manter somente checkpoints estáveis.

O RL só será promovido se superar a heurística em win rate e mantiver melhora em
lucro, erros e variância sob múltiplas sementes.

### Fase 6 — Híbrida

```text
estado -> RL escolhe política do dia -> planner escolhe tarefas
       -> executor executa -> monitor verifica segurança
```

A heurística terá autoridade para intervir em risco de fuga, planta perdida,
falta de alimento, shed cheio, caixa insuficiente, ação inválida, rota ausente e
final da temporada. Falhas repetidas suspendem RL pelo restante do dia e ativam a
política conservadora.

### Fase 7 — Submissão

Validar `env.run(["main.py", "random"])` e self-play; tamanho menor que 100 MiB;
tempo, memória, imports, ausência de internet e caminhos locais. Manter versões
`v1` (segura), `v2` (econômica), `v3` (RL), `v4` (híbrida) e `final` (melhor
comprovada). Não submeter experimentos sem benchmark.

## 6. Cronograma até 30/09/2026

| Período | Entrega | Gate de decisão |
|---|---|---|
| 18–20 ago | Regras, schema, estrutura e ambiente | regras aceitas e dependências confirmadas |
| 21–24 ago | agente mínimo, runner e métricas | partida local completa |
| 25–30 ago | estado normalizado e executor | zero falhas fatais no cenário básico |
| 31 ago–06 set | heurística de abertura, produção e mercado | baseline benchmarkado |
| 07–13 set | dataset e ambiente RL | episódios reproduzíveis |
| 14–20 set | RL, snapshots e comparação | RL aprovado ou descartado |
| 21–25 set | híbrida e testes de falha | candidata estável |
| 26–29 set | pacote e submissões incrementais | limites Kaggle validados |
| 30 set | congelamento da final | versão final e recuperação prontas |

## 7. Critérios globais de aceite

- completa 720 turnos sem erro;
- não perde agentes por falhas evitáveis;
- liquida estoque ao final;
- evita ações inválidas;
- possui benchmarks reproduzíveis;
- compara engines com as mesmas sementes;
- cabe no pacote Kaggle;
- mantém uma versão conservadora de recuperação.

## 8. Decisões abertas para revisão

1. Qual é o nome/schema oficial do ambiente?
2. Quais ações e observações são válidas exatamente?
3. O horizonte é sempre 720 turnos?
4. `starter` existe como oponente oficial?
5. Qual é o orçamento de CPU/memória/tamanho?
6. RL é obrigatório ou apenas uma hipótese de melhoria?
7. Qual limiar define “melhoria significativa”?
8. Quantas submissões serão usadas antes do congelamento?

