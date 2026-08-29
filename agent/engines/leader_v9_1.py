"""Leader V9.1: High-Margin Crops, Wheat Monopoly & Deterministic Crop Dusta Opening.

Otimizações principais baseadas nos replays do Crop Dusta:
1. Abertura Determinística Day 0: Contratação de 4 manos, compra de animais
   e sementes de WHEAT/MELON no step 1, 2 e 3.
2. WHEAT Monopoly: Redução da penalidade de fricção do trigo para incentivar
   plantios em larga escala.
3. MELON Suppression: Remoção do boost de ROI para MELON para evitar plantios
   ineficientes após o Dia 5.
4. Late-Game Carrot Pivot: Foco em WHEAT e CARROT após o Dia 20.
"""

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v9 import LeaderV9Config, LeaderV9Engine

_V91_ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}


class LeaderV91Config(LeaderV9Config):
    pass


class LeaderV91Engine(LeaderV9Engine):
    def __init__(self, config: LeaderV91Config | None = None) -> None:
        self.v91_config = config or LeaderV91Config()
        super().__init__(self.v91_config)

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Abertura Determinística do Crop Dusta no Dia 0
        if state.day == 0:
            if state.hour == 1 and not self._animal_count(state) and not any(state.shed.values()):
                return [
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_ANIMAL", "SHEEP", 2],
                    ["BUY_SEED", "MELON", 5],
                    ["BUY_SEED", "WHEAT", 9],
                ]
            elif state.hour == 2:
                # Step 2: Compra ração + 1 COW adicional
                return [
                    ["BUY_PRODUCT", "WHEAT", 4],
                    ["BUY_ANIMAL", "COW", 1],
                ]
            elif state.hour == 3:
                # Step 3: Compra ração adicional
                return [
                    ["BUY_PRODUCT", "WHEAT", 4],
                ]
            return []

        # Para outros dias, executa a lógica da V9
        return super()._build_market_orders(state, goals, tasks)

    def _calculate_marginal_tile_roi(
        self, crop: str, state: NormalizedState, horizon: int, current_planned_tiles: int
    ) -> float:
        # Acessa a ROI base da V8 (para contornar a penalidade pesada de trigo da V9)
        base_roi = super(LeaderV9Engine, self)._calculate_marginal_tile_roi(
            crop, state, horizon, current_planned_tiles
        )

        # 1. Monopólio de WHEAT: Reduz a penalidade de fricção para no máximo 1.5
        # (quase insignificante)
        if crop == "WHEAT":
            labor_friction_penalty = 1.5
            return max(0.0, base_roi - labor_friction_penalty)

        # 2. CARROT: Reduz a penalidade de fricção de 6.0 para 3.0 no late game
        # para incentivar o pivot
        elif crop == "CARROT":
            labor_friction_penalty = 3.0
            return max(0.0, base_roi - labor_friction_penalty)

        # 3. STRAWBERRY: Boost early game para acelerar capital
        elif crop == "STRAWBERRY":
            if state.day < 12:
                return base_roi * 1.5
            # Desincentiva plantios tardios que não rendem múltiplos ciclos
            elif state.day > 18:
                return 0.0

        # 4. MELON: Suprime MELON após o dia 5, pois tem maturação longa (10 dias)
        # e baixa versatilidade
        elif crop == "MELON":
            if state.day < 5:
                return base_roi * 1.3
            else:
                return 0.0

        # 5. TOMATO: Bloqueia plantio tardio (maturação de 8 dias)
        elif crop == "TOMATO" and state.day > 20:
            return 0.0

        return base_roi
