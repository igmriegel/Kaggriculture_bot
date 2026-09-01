"""Leader V9.2: Calibrated ROI Engine with Adaptive Opening.

Otimizações principais baseadas na auditoria contra a V9:
1. Wheat Penalty Calibrado: Ajustado para -6.0 (em vez de -12.0 na V9 ou -1.5 na V9.1).
2. Melon Cutoff Calibrado: Ajustado para Day 12 (em vez de Day 15 na V9 ou Day 5 na V9.1).
3. Abertura Adaptativa: 2 contratações com mix de sementes responsivo aos shops.
4. Late-Game Carrot Pivot: Ajustes calibrados nas penalidades de Carrot e cutoffs
   de Strawberry/Tomato.
"""

from dataclasses import dataclass
from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v9 import LeaderV9Config, LeaderV9Engine


@dataclass(frozen=True)
class LeaderV92Config(LeaderV9Config):
    wheat_labor_penalty: float = 12.0     # Was 12.0 in V9, 1.5 in V9.1
    carrot_labor_penalty: float = 4.0     # Was 6.0 in V9, 3.0 in V9.1
    carrot_late_penalty: float = 2.0      # After day 16
    melon_cutoff_day: int = 18            # Was 12 in V9.2 baseline, 15 in V9
    strawberry_cutoff_day: int = 20       # Was none in V9, 18 in V9.1
    tomato_cutoff_day: int = 22           # Was none in V9, 20 in V9.1
    day0_hires: int = 2                   # Was 1 in V9, 4 in V9.1
    day0_extra_cow: bool = True           # Buy 3rd cow on step 2


class LeaderV92Engine(LeaderV9Engine):
    def __init__(self, config: LeaderV92Config | None = None) -> None:
        self.v92_config = config or LeaderV92Config()
        super().__init__(self.v92_config)

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders = super()._sales(state, projected)

        # Mid-game liquidation: Sell MELON continuously when harvested to unlock cash flow
        if not self._closing(state):
            melon_in_shed = state.shed.get("MELON", 0)
            already_selling_melon = any(
                len(o) > 1 and o[0] == "SELL" and o[1] == "MELON" for o in orders
            )
            if melon_in_shed >= 2 and not already_selling_melon:
                if len(orders) < self.v8_config.max_orders:
                    orders.append(["SELL", "MELON", melon_in_shed])

        return orders

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Abertura Adaptativa no Dia 0
        if state.day == 0:
            if state.hour == 1 and not self._animal_count(state) and not any(state.shed.values()):
                has_strawberry_shop = any("STRAWBERRY" in SHOPS.get(s, ()) for s in state.shops)
                orders = [["HIRE"], ["HIRE"]]
                orders.append(["BUY_ANIMAL", "COW", 2])
                orders.append(["BUY_ANIMAL", "SHEEP", 2])
                if has_strawberry_shop:
                    orders.append(["BUY_SEED", "STRAWBERRY", 4])
                    orders.append(["BUY_SEED", "WHEAT", 6])
                else:
                    orders.append(["BUY_SEED", "MELON", 4])
                    orders.append(["BUY_SEED", "WHEAT", 6])
                return orders
            elif state.hour == 2 and self.v92_config.day0_extra_cow:
                # Step 2: Compra ração + 1 COW adicional (mesmo que V9.1)
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
        # Acessa a ROI base da V8 (para contornar a penalidade pesada de trigo/carrot da V9)
        base_roi = super(LeaderV9Engine, self)._calculate_marginal_tile_roi(
            crop, state, horizon, current_planned_tiles
        )

        cfg = self.v92_config
        if crop == "WHEAT":
            return max(0.0, base_roi - cfg.wheat_labor_penalty)

        elif crop == "CARROT":
            penalty = cfg.carrot_late_penalty if state.day > 16 else cfg.carrot_labor_penalty
            return max(0.0, base_roi - penalty)

        elif crop == "STRAWBERRY":
            if state.day <= cfg.strawberry_cutoff_day:
                return base_roi * (1.5 if state.day < 12 else 1.25)
            else:
                return 0.0

        elif crop == "MELON":
            if state.day <= cfg.melon_cutoff_day:
                return base_roi * 1.3
            else:
                return 0.0

        elif crop == "TOMATO" and state.day > cfg.tomato_cutoff_day:
            return 0.0

        return base_roi
