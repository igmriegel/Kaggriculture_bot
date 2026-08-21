# Harness development and evaluation contract

This is the canonical harness contract. Read
[`HARNESS_IMPLEMENTATION.md`](HARNESS_IMPLEMENTATION.md) for the current code
status and task-sized implementation map.

**Status:** contract under implementation  
**Goal:** provide a reliable execution layer before expanding competitive engines.

O harness será o contrato entre o ambiente Kaggle, o agente e a avaliação. Ele
must allow isolated engine tests, complete episodes, seed reproduction, and
comparable evidence. The current partial implementation is tracked separately
so this contract remains stable while adapters evolve.

## 1. Escopo do harness

### Incluído

- adaptador para o ambiente oficial;
- execução de uma partida e de lotes de partidas;
- seleção de agente e oponente;
- controle de seed/configuração;
- captura de ações, observações e resultado;
- validação de ações antes do envio;
- contagem de exceções e ações inválidas;
- métricas agregadas e por episódio;
- logs opcionais e artefatos versionados;
- cenários determinísticos de smoke test.

### Fora do escopo inicial

- treinamento de RL;
- otimização da estratégia;
- simulação fictícia que substitua o ambiente oficial;
- dependência de notebooks;
- alteração automática de código ou submissão no Kaggle.

## 2. Interfaces conceituais

```text
EnvironmentAdapter
  reset(seed, configuration) -> EpisodeContext
  step(action) -> Observation
  finished() -> bool
  result() -> RawResult

AgentAdapter
  act(observation) -> Action

EpisodeRunner
  run(agent, opponent, seed, configuration) -> EpisodeRecord

BenchmarkRunner
  run(matrix_of_scenarios) -> BenchmarkReport
```

Os nomes acima são contratos de planejamento, não decisão final de módulos. O
schema de `Observation`, `Action` e `RawResult` deve ser derivado da competição
antes da implementação.

## 3. Fluxo de uma partida

```text
configuração + seed
        ↓
criar ambiente e agentes
        ↓
obter observação inicial
        ↓
validar observação e chamar agente
        ↓
validar ação e enviar ao ambiente
        ↓
registrar turn, latência, ação e erro
        ↓
repetir até término ou limite de segurança
        ↓
normalizar resultado e gerar EpisodeRecord
```

O harness deve distinguir claramente:

- erro do ambiente;
- exceção do agente;
- ação malformada;
- ação válida rejeitada pelo ambiente;
- término normal;
- término por limite de segurança.

## 4. Contrato de segurança

Antes de enviar uma ação, o harness deverá:

1. confirmar que o retorno tem o tipo esperado;
2. confirmar que a ação pertence ao conjunto permitido;
3. confirmar campos obrigatórios e tipos;
4. substituir por `PASS` quando houver fallback definido;
5. registrar o motivo da substituição;
6. nunca mascarar o erro no relatório final.

O limite de turnos deve ser configurável, com valor padrão igual ao horizonte
oficial depois de confirmado. Deve existir também um limite de tempo por ação e
um watchdog para evitar episódio preso.

## 5. Registro mínimo por turno

Cada turno deve poder registrar, com logging configurável:

| Campo | Observação |
|---|---|
| `episode_id` | identificador reprodutível |
| `seed` | seed efetivamente usada |
| `turn` | índice do turno |
| `agent` / `opponent` | versões ou nomes |
| `observation_hash` | rastreabilidade sem exigir logs gigantes |
| `action_raw` | retorno original do agente |
| `action_sent` | ação efetivamente enviada |
| `fallback_reason` | vazio quando não houve fallback |
| `latency_ms` | tempo da decisão |
| `exception` | tipo e mensagem, se houver |

O modo detalhado poderá salvar observações completas. O modo resumido deve ser o
padrão para não gerar artefatos excessivos.

## 6. Registro mínimo por episódio

- seed e configuração;
- agente e oponente;
- status: vitória, derrota, empate, erro ou incompleto;
- turnos executados;
- duração total e latência máxima/média;
- dinheiro/lucro final, quando disponíveis;
- erros, exceções, ações inválidas e fallbacks;
- perdas de plantas/animais e estoque descartado;
- caminho do log e versão do harness.

Campos desconhecidos devem ser nulos, nunca inventados. O harness deve preservar
o resultado bruto para permitir uma normalização posterior.

## 7. Cenários de teste

### Smoke

- observação inicial válida;
- agente que sempre retorna `PASS`;
- agente que retorna ação válida conhecida;
- agente que retorna tipo inválido;
- agente que lança exceção;
- episódio que atinge o fim normal.

### Robustez

- observação vazia ou com campos desconhecidos;
- ação incompleta;
- ação fora do domínio;
- ambiente que rejeita uma ação;
- timeout do agente;
- seed repetida produzindo o mesmo resultado;
- seed diferente sendo aceita sem reutilizar estado.

### Competição

- `main.py` contra `random`;
- `main.py` contra si próprio;
- múltiplos episódios por engine;
- lote com seeds explícitas;
- execução sem acesso à internet;
- execução a partir de diretório diferente do repositório.

## 8. CLI planejada

```bash
python -m harness.run \
  --agent <nome> \
  --opponent <nome> \
  --episodes 100 \
  --seed 42 \
  --output reports/run.json
```

Comandos planejados:

- `run`: executar episódios;
- `smoke`: validar contrato básico;
- `benchmark`: executar uma matriz de engines/oponentes/seeds;
- `report`: agregar registros existentes;
- `validate-submission`: verificar pacote e limites.

As opções devem falhar explicitamente para configurações inválidas e imprimir um
resumo curto adequado para CI.

## 9. Relatório de benchmark

O relatório deve apresentar, por engine e oponente:

| Engine | Oponente | Episódios | Win rate | Lucro médio | Desvio | Erros | Inválidas | Latência |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| — | — | — | — | — | — | — | — | — |

O relatório também deve expor seeds usadas, episódios incompletos e motivo de
exclusão. Nenhum resultado deve ser comparado se as matrizes de seeds forem
diferentes sem essa ressalva.

## 10. Ordem de construção do harness

1. confirmar contrato do ambiente oficial;
2. definir modelos de registro e códigos de erro;
3. implementar adaptador mínimo;
4. implementar `PASS` e validação de ação;
5. implementar runner de um episódio;
6. adicionar seed, timeout e logs;
7. adicionar cenários smoke/robustez;
8. adicionar lotes e agregação;
9. adicionar comparação de engines;
10. adicionar validação do pacote de submissão.

## 11. Critérios de aceite do harness

- executa um episódio completo no ambiente oficial;
- reproduz o resultado quando seed e configuração são iguais;
- distingue erro do agente de erro do ambiente;
- nunca envia ação malformada sem registrar fallback;
- encerra episódios presos por timeout/limite;
- produz registro por episódio e relatório agregado;
- executa smoke tests sem depender de Kaggle remoto;
- não exige que uma engine competitiva esteja pronta;
- não contém lógica específica de estratégia no runner.

## 12. Decisões pendentes

1. O ambiente será importado diretamente por `kaggle_environments` ou por um
   adaptador fornecido pela competição?
2. Qual formato de seed o ambiente aceita?
3. Oponentes são nomes, arquivos ou funções?
4. O ambiente permite timeout por turno?
5. Quais campos do resultado são oficiais?
6. Qual formato de log será aceito: JSON, JSONL ou ambos?
7. Onde serão armazenados relatórios sem entrar no pacote de submissão?
