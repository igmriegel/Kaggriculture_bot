from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from agent.core.state import NormalizedState
from agent.engines.leader_v9 import LeaderV9Engine
from agent.engines.leader_v10 import LeaderV10Engine, V10Config
from agent.harness.adapters.kaggle import KaggleEnvironmentAdapter


class KaggricultureParamGymEnv(gym.Env):
    """
    Gymnasium environment that optimizes V10 parameters dynamically day-by-day.
    The action space is a continuous vector of V10Config parameters.
    The observation space is a normalized state vector representing the farm status.
    Each gym step represents 1 Day (24 game turns).
    """

    metadata = {"render_modes": []}

    def __init__(self, opponent_class: Any = LeaderV9Engine) -> None:
        super().__init__()
        self.opponent_class = opponent_class

        # Action space: 26 parameters mapped to [-1, 1]
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(26,), dtype=np.float32)

        # Observation space: 15 features
        # [day, money/50k0, unlocked_quads/4, workers/5, cows/10, sheep/10,
        #  wheat_p, carrot_p, tomato_p, strawberry_p, melon_p,
        #  opp_money/50k, opp_workers/5, opp_cows/10, opp_sheep/10]
        self.observation_space = spaces.Box(low=0.0, high=10.0, shape=(15,), dtype=np.float32)

        self.adapter = None
        self.runner = None
        self.state = None
        self.seed_val = None
        self.current_day = 0
        self.last_money = 3000

    def _get_obs(self, norm_state: NormalizedState) -> np.ndarray:
        prices = norm_state.prices
        opp_cows = sum(1 for t in norm_state.opponent_tiles if t.animal == "COW")
        opp_sheep = sum(1 for t in norm_state.opponent_tiles if t.animal == "SHEEP")

        obs = np.array(
            [
                norm_state.day / 30.0,
                norm_state.money / 50000.0,
                len(norm_state.unlocked_quadrants) / 4.0,
                (1 + len(norm_state.hand_positions)) / 5.0,
                sum(1 for t in norm_state.tiles if t.animal == "COW") / 10.0,
                sum(1 for t in norm_state.tiles if t.animal == "SHEEP") / 10.0,
                prices.get("WHEAT", 25) / 25.0,
                prices.get("CARROT", 35) / 35.0,
                prices.get("TOMATO", 60) / 60.0,
                prices.get("STRAWBERRY", 120) / 120.0,
                prices.get("MELON", 250) / 250.0,
                norm_state.opponent_money / 50000.0,
                len(norm_state.opponent_tiles) / 100.0,  # approximate opponent scale
                opp_cows / 10.0,
                opp_sheep / 10.0,
            ],
            dtype=np.float32,
        )
        return obs

    def reset(
        self, seed: int | None = None, options: dict | None = None
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.seed_val = seed or np.random.randint(1, 100000)

        opp_eng = self.opponent_class()
        self.adapter = KaggleEnvironmentAdapter(opponent=opp_eng.act)

        # We start the Kaggle Environment
        self.last_raw_obs = self.adapter.reset(seed=self.seed_val)
        self.state = NormalizedState.from_observation(self.last_raw_obs)
        self.current_day = 0
        self.last_money = self.state.money

        return self._get_obs(self.state), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        # Map actions from [-1, 1] to target parameter ranges
        # Suggestions mapping:
        params = {
            "closing_day": int(np.round(23 + (action[0] + 1) * 2.5)),  # 23 to 28
            "closing_maintenance_threshold": int(np.round(8 + (action[1] + 1) * 4)),  # 8 to 16
            "closing_workers_max": int(np.round(3 + (action[2] + 1) * 1.0)),  # 3 to 5
            "closing_workers_min": int(np.round(1 + (action[3] + 1) * 1.0)),  # 1 to 3
            "min_cash_buffer_livestock": int(200 + (action[4] + 1) * 300),  # 200 to 800
            "double_animal_buy_threshold": int(1200 + (action[5] + 1) * 500),  # 1200 to 2200
            "melon_roi_multiplier": float(1.0 + (action[6] + 1) * 0.5),  # 1.0 to 2.0
            "strawberry_roi_multiplier": float(1.0 + (action[7] + 1) * 0.5),  # 1.0 to 2.0
            "speculation_hold_threshold": float(0.70 + (action[8] + 1) * 0.125),  # 0.70 to 0.95
            "speculation_min_liquidity": int(1000 + (action[9] + 1) * 750),  # 1000 to 2500
            "opponent_crop_penalty": float(0.01 + (action[10] + 1) * 0.07),  # 0.01 to 0.15
            # New 14 parameters mapping:
            "feed_buffer_threshold": int(np.round(2 + (action[11] + 1) * 2)),  # 2 to 6
            "feed_buy_min_money": int(np.round(50 + (action[12] + 1) * 125)),  # 50 to 300
            "feed_buffer_days": int(np.round(1 + (action[13] + 1) * 2)),  # 1 to 5
            "hire_workload_threshold": int(np.round(6 + (action[14] + 1) * 6)),  # 6 to 18
            "hire_min_animals": int(np.round(1 + (action[15] + 1) * 2)),  # 1 to 5
            "land_unlock_saturation_ratio": float(0.50 + (action[16] + 1) * 0.20),  # 0.50 to 0.90
            "seed_buffer_per_tile": int(np.round(10 + (action[17] + 1) * 25)),  # 10 to 60
            "animal_cow_sheep_ratio": float(1.5 + (action[18] + 1) * 1.75),  # 1.5 to 5.0
            "animal_sheep_cow_ratio": float(1.0 + (action[19] + 1) * 1.5),  # 1.0 to 4.0
            "wheat_feed_buffer_per_animal": int(np.round(1 + (action[20] + 1) * 1.5)),  # 1 to 4
            "max_fertilizer_to_keep": int(np.round(1 + (action[21] + 1) * 2.5)),  # 1 to 6
            "front_run_opponent_harvest_threshold": int(
                np.round(2 + (action[22] + 1) * 4)
            ),  # 2 to 10
            "clearance_day_threshold": int(np.round(25 + (action[23] + 1) * 2)),  # 25 to 29
            "continuous_sale_min_amount": int(np.round(1 + (action[24] + 1) * 2)),  # 1 to 5
            # We map 25 parameters, marginal_sale_price_ratio_floor is mapped from action[24] or we can map it too.
            # Let's map continuous_sale_min_amount as action[23] and clearance_day_threshold as action[22]...
            # Wait, there are 14 parameters, so indexes from 11 to 24 are 14 slots (11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24).
            # Let's count them:
            # 11: feed_buffer_threshold
            # 12: feed_buy_min_money
            # 13: feed_buffer_days
            # 14: hire_workload_threshold
            # 15: hire_min_animals
            # 16: land_unlock_saturation_ratio
            # 17: seed_buffer_per_tile
            # 18: animal_cow_sheep_ratio
            # 19: animal_sheep_cow_ratio
            # 20: wheat_feed_buffer_per_animal
            # 21: max_fertilizer_to_keep
            # 22: front_run_opponent_harvest_threshold
            # 23: clearance_day_threshold
            # 24: continuous_sale_min_amount
            "marginal_sale_price_ratio_floor": float(
                0.20 + (action[25] + 1) * 0.20
            ),  # 0.20 to 0.60
        }

        config = V10Config(**params)
        agent_eng = LeaderV10Engine(config=config)

        # Simulate exactly 1 day (24 turns) using this config
        for _ in range(24):
            if self.adapter.finished():
                break
            # Run one micro turn
            action_raw = agent_eng.act(self.last_raw_obs)
            # Send step
            self.last_raw_obs = self.adapter.step(action_raw)

        # Get new state
        self.state = NormalizedState.from_observation(self.last_raw_obs)
        self.current_day = self.state.day

        # Reward calculation: cash margin gain scaled to prevent gradient explosion
        current_money = self.state.money
        reward = float(current_money - self.last_money) / 1000.0
        self.last_money = current_money

        terminated = self.adapter.finished()
        truncated = self.current_day >= 30

        # Add final game margin bonus at the end
        if terminated or truncated:
            res = self.adapter.result()
            rewards = res.get("rewards", [0, 0])
            margin = (rewards[0] - rewards[1]) / 1000.0
            reward += float(margin)  # heavily incentivize winning

        return self._get_obs(self.state), reward, terminated, truncated, {}
