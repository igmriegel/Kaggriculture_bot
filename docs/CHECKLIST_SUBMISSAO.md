# Checklist de submissão

## Regras e ambiente

- [ ] regras da competição aceitas manualmente;
- [ ] schema oficial conferido;
- [ ] limites de CPU, memória, tempo e tamanho registrados;
- [ ] dependências permitidas confirmadas;
- [ ] acesso à internet e persistência verificados.

## Pacote

- [ ] `main.py` na raiz;
- [ ] somente uma engine estável selecionada;
- [ ] modelos aprovados em `models/`;
- [ ] sem notebooks, dados brutos ou código de treinamento;
- [ ] sem caminhos absolutos ou arquivos fora do pacote;
- [ ] tamanho menor que 100 MiB.

## Validação

- [ ] partida contra `random` completa 720 turnos;
- [ ] partida `main.py` contra `main.py` completa;
- [ ] nenhuma ação malformada;
- [ ] fallback `PASS` testado;
- [ ] cenários de dinheiro, espaço, alimento, rota e shed cobertos;
- [ ] benchmark reproduzível arquivado;
- [ ] versão conservadora de recuperação pronta.

## Controle de versões

- [ ] `v1` segura;
- [ ] `v2` econômica;
- [ ] `v3` RL, somente se aprovada;
- [ ] `v4` híbrida, somente se aprovada;
- [ ] `final` é a melhor versão comprovada;
- [ ] não enviar experimento sem benchmark local.

