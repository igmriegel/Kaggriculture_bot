# Kaggle Optimization & Training Pipeline

Este guia detalha o pipeline automatizado para compilar, fazer o upload e rodar treinamentos de Reinforcement Learning (PPO/Stable-Baselines3) e Otimização Genética (Optuna) usando as CPUs e GPUs gratuitas do Kaggle.

---

## Prerrequisitos

1. **Instalar a Kaggle API**:
   Verifique se as credenciais do Kaggle estão instaladas localmente em `~/.kaggle/kaggle.json`. Se não, faça o download do token API nas configurações do seu perfil do Kaggle.
2. **Permissão de arquivos**:
   Certifique-se de que o arquivo de token tem as permissões corretas:
   ```bash
   chmod 600 ~/.kaggle/kaggle.json
   ```

---

## Pipeline no Makefile

Dividimos o fluxo em etapas fáceis de rodar usando o `Makefile` do projeto.

### 1. Compilar e Fazer Upload do Pacote de Código
Para empacotar o código local em um arquivo distribuível `.whl` e subir para o dataset privado no Kaggle:
```bash
make kaggle-deploy-code
```
*(Esse comando roda o build, copia os scripts de otimização/runner e atualiza o dataset do Kaggle).*

### 2. Disparar a Execução na Nuvem (Kaggle Kernel)
Para iniciar a execução do notebook remotamente nas instâncias de GPU/CPU do Kaggle:
```bash
make kaggle-run
```

### 3. Monitorar o Status do Job
Para acompanhar o andamento da execução (se está na fila, rodando ou concluído):
```bash
make kaggle-status
```

### 4. Recuperar Resultados e Modelos
Quando o job estiver finalizado (`Complete`), baixe as configurações otimizadas (JSON) ou o modelo PPO treinado (.zip) diretamente para a pasta `reports/kaggle/`:
```bash
make kaggle-retrieve
```

---

## Estrutura do Runner de Treinamento (`kaggle_runner.py`)

O script `scripts/kaggle_runner.py` suporta dois modos principais executados no Kaggle:

1. **Reinforcement Learning (`--mode rl`)**:
   Utiliza um ambiente customizado Gymnasium (`KaggricultureParamGymEnv`) para treinar um modelo **PPO (Stable-Baselines3)** a ajustar dinamicamente os parâmetros da engine `LeaderV10Engine` dia após dia, maximizando a margem de lucros contra o oponente `LeaderV9`.
2. **Otimização Genética (`--mode optuna`)**:
   Roda buscas em larga escala no Kaggle utilizando CMA-ES e TPE do Optuna para encontrar os valores estáticos ideais de inicialização.
