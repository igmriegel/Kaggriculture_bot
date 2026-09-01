"""MCTS & Lookahead Search Engine wrapping base engines with forward simulation."""

from __future__ import annotations

from typing import Any

from agent.core.simulation import ForwardSimulator, evaluate_state_value
from agent.core.state import NormalizedState
from agent.engines.leader_v10 import LeaderV10Engine


class MCTSLookaheadEngine:
    """Engine using forward lookahead search to optimize unit action choices."""

    def __init__(self, base_engine: Any | None = None, search_depth: int = 1) -> None:
        self.base_engine = base_engine or LeaderV10Engine()
        self.search_depth = search_depth
        self.simulator = ForwardSimulator()

    def act(self, obs: dict[str, Any]) -> dict[str, list[Any]]:
        # Get base recommended action
        base_action_dict = self.base_engine.act(obs)

        try:
            state = NormalizedState.from_observation(obs)
        except Exception:
            return base_action_dict

        # Evaluate candidate farmer actions
        candidates = self._generate_candidate_farmer_actions(state, base_action_dict)
        if not candidates:
            return base_action_dict

        best_score = float("-inf")
        best_farmer_cmd: list[Any] = base_action_dict.get("farmer", ["PASS"])

        config = getattr(self.base_engine, "v10_config", getattr(self.base_engine, "config", None))
        for cmd in candidates:
            simulated = self.simulator.step_action(state, tuple(cmd))
            score = evaluate_state_value(simulated, config=config)
            if score > best_score:
                best_score = score
                best_farmer_cmd = cmd

        result = dict(base_action_dict)
        result["farmer"] = best_farmer_cmd
        return result

    def _generate_candidate_farmer_actions(
        self, state: NormalizedState, base_action_dict: dict[str, Any]
    ) -> list[list[Any]]:
        base_farmer = base_action_dict.get("farmer", ["PASS"])
        candidates: list[list[Any]] = [base_farmer]

        tile = state.tile_at_position()
        if tile and tile.kind == "PLANT":
            if tile.yield_units > 0:
                candidates.append(["HARVEST"])
            elif not tile.watered_today:
                candidates.append(["WATER"])

        # Basic movement candidates
        x, y = state.position
        if y > 0:
            candidates.append(["NORTH"])
        if y < state.board_size - 1:
            candidates.append(["SOUTH"])
        if x > 0:
            candidates.append(["WEST"])
        if x < state.board_size - 1:
            candidates.append(["EAST"])

        return candidates
