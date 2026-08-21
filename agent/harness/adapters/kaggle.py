"""Lazy adapter for the official advanced Kaggriculture environment."""

import importlib
from collections.abc import Callable
from typing import Any


class KaggleEnvironmentAdapter:
    """Wrap ``kaggle_environments.make`` behind the harness adapter protocol.

    The dependency is imported lazily so unit-only development does not require
    the optional native competition stack.
    """

    def __init__(self, opponent: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self._opponent = opponent or _pass_agent
        self._environment: Any = None
        self._player = 0

    def reset(
        self, seed: int | None = None, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            make = importlib.import_module("kaggle_environments").make
        except ModuleNotFoundError as exc:
            raise RuntimeError("install the optional 'competition' dependency group") from exc
        config = dict(configuration or {})
        if seed is not None:
            config["seed"] = seed
        self._environment = make("kaggriculture", configuration=config, debug=True)
        self._environment.reset(num_agents=2)
        return _observation(self._environment, self._player)

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        if self._environment is None:
            raise RuntimeError("reset must be called before step")
        opponent_action = self._opponent(_observation(self._environment, 1))
        self._environment.step([action, opponent_action])
        return _observation(self._environment, self._player)

    def finished(self) -> bool:
        return bool(self._environment and self._environment.done)

    def result(self) -> Any:
        if self._environment is None:
            return None
        rewards = [state.reward for state in self._environment.state]
        winner = 0 if rewards[0] > rewards[1] else 1 if rewards[1] > rewards[0] else None
        return {"winner": winner, "rewards": rewards, "money": rewards[self._player]}


def _observation(environment: Any, player: int) -> dict[str, Any]:
    observation = environment.state[player].observation
    return dict(observation)


def _pass_agent(observation: dict[str, Any]) -> dict[str, Any]:
    del observation
    return {"farmer": ["PASS"], "market": []}
