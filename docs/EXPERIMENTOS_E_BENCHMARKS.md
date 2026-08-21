# Experimentos e benchmarks

## Protocolo

Toda comparação deve usar as mesmas sementes, horizonte, configuração e
oponentes. Registrar código/versão da engine, data, seed, resultado, lucro,
variância, erros, ações inválidas, tempo, perdas, overflow, fertilizante, terra,
mãos e volume vendido por produto.

## Matriz mínima

| Engine | Oponentes | Episódios | Seeds | Critério |
|---|---|---:|---|---|
| PASS | random | 100 | fixa + variações | validade e completude |
| Heurística | pass, random, starter, própria | 100 cada | múltiplas | erro próximo de zero e ganho sobre starter |
| RL | mesmos da heurística | 100 cada | mesmas | superar baseline em múltiplas seeds |
| Híbrida | mesmos da heurística | 100 cada | mesmas | maior win rate sem regressão de segurança |

## Hipóteses

1. Uma heurística conservadora vence estratégias que geram overflow ou perdem
   animais.
2. Decisões estratégicas diárias reduzem o espaço de ação do RL sem sacrificar
   decisões críticas.
3. A intervenção da heurística reduz erros do RL sem eliminar seus ganhos.

## Critérios de promoção

Uma engine só substitui a anterior quando melhora win rate no conjunto de seeds
de validação, não aumenta significativamente a taxa de erro e não apresenta
regressão material em lucro ou estabilidade. Resultados positivos em uma única
seed não são suficientes.

