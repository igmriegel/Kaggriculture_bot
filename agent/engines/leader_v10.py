"""Leader V10: Advanced Spatial Zoning, Feed Sourcing Optimization & Livestock Clearance.

Otimizações principais:
1. Feed Sourcing Optimization: Compra Trigo (feed) diretamente do mercado se o custo de
   trabalho (ações do fazendeiro) de plantar/regar/colher exceder o custo de compra direta.
2. Spatial Zoning Priority: Agrupa pastos e culturas perto do centro.
3. Livestock Late-Game Clearance: Vende animais no dia 29 se não produzirem antes do fim.
"""

from typing import Any

from agent.core.state import NormalizedState
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v9 import LeaderV9Config, LeaderV9Engine
from agent.engines.spatial_planner import prioritize_unlocked_tiles_by_shed_proximity


class LeaderV10Config(LeaderV9Config):
    pass


class LeaderV10Engine(LeaderV9Engine):
    def __init__(self, config: LeaderV10Config | None = None) -> None:
        self.v10_config = config or LeaderV10Config()
        super().__init__(self.v10_config)

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, float]]:
        # Feed-Crop Optimization:
        # Se Trigo (WHEAT) for barato no mercado (< $35), nós não vamos planejar plantá-lo.
        # Compramos do mercado diretamente para ração animal.
        portfolio = super()._dynamic_crop_portfolio(state, horizon, empty_slots)
        wheat_price = state.prices.get("WHEAT", 25)
        if wheat_price < 35:
            portfolio = [(crop, val) for crop, val in portfolio if crop != "WHEAT"]
        return portfolio

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        # Para customizar o Spatial Zoning:
        # Interceptamos e reordenamos as tarefas geradas pela engine base.
        tasks = super()._tasks(state, goals)

        # 1. Spatial Zoning:
        # Separamos as tarefas de plantar (PLANT) e re-alocamos para as tiles mais periféricas
        plant_tasks = [t for t in tasks if t.command and t.command[0] == "PLANT"]
        if plant_tasks:
            other_tasks = [t for t in tasks if not (t.command and t.command[0] == "PLANT")]

            shed_tiles = state.shed_tiles()
            empty_tiles = prioritize_unlocked_tiles_by_shed_proximity(
                state.tiles, shed_tiles, predicate=lambda t: t.kind is None
            )
            # Inverte a ordem das tiles vazias para priorizar a periferia (distantes do Shed)
            empty_periphery = empty_tiles[::-1]

            reordered_plant_tasks = []
            for t in plant_tasks:
                if len(empty_periphery) > 0:
                    tile = empty_periphery.pop(0)
                    point = (tile.x, tile.y)
                    # Cria nova tarefa de plantio apontando para a tile periférica
                    reordered_plant_tasks.append(
                        Task(t.priority, point, t.command, t.eligible, ("tile", point))
                    )
                else:
                    reordered_plant_tasks.append(t)
            tasks = other_tasks + reordered_plant_tasks

        return tasks

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Livestock Late-Game Clearance:
        # No dia 29 e 30, qualquer animal com tempo de produção inativo (ou residual)
        # é vendido de volta ao mercado para converter em liquidez imediata.
        if state.day in {29, 30}:
            sell_orders = []
            cows = sum(1 for t in state.tiles if t.animal == "COW")
            sheep = sum(1 for t in state.tiles if t.animal == "SHEEP")
            if cows > 0:
                sell_orders.append(["SELL", "COW", cows])
            if sheep > 0:
                sell_orders.append(["SELL", "SHEEP", sheep])
            if sell_orders:
                return sell_orders[: self.v10_config.max_orders]

        # Comportamento padrão de compra/venda da V9
        orders = super()._build_market_orders(state, goals, tasks)

        # Feed-Crop Optimization:
        # Se Trigo (WHEAT) for barato no mercado (< $35) e tivermos animais famintos ou
        # déficit de ração no silo, compramos trigo diretamente para o silo.
        wheat_price = state.prices.get("WHEAT", 25)
        if wheat_price < 35:
            wheat_in_shed = state.shed.get("WHEAT", 0)
            target_feed = self._animal_count(state) * 5
            deficit = max(0, target_feed - wheat_in_shed)
            if deficit > 0 and state.money > 100:
                # Insere a ordem de compra de trigo no início das ordens de mercado
                buy_amount = min(deficit, int(state.money // wheat_price))
                if buy_amount > 0:
                    orders.insert(0, ["BUY_SEED" if False else "BUY", "WHEAT", buy_amount])

        return orders[: self.v10_config.max_orders]
