"""Explicit registries that make harness extensions discoverable."""

from collections.abc import Iterator

from agent.harness.models import Scenario
from agent.harness.protocols import Agent, EnvironmentAdapter, Reporter


class Registry[T]:
    """Named registry with actionable lookup and duplicate diagnostics."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, T] = {}

    def register(self, name: str, item: T) -> T:
        if not name or name.strip() != name:
            raise ValueError(f"{self.kind} name must be non-empty and trimmed")
        if name in self._items:
            raise ValueError(f"{self.kind} '{name}' is already registered")
        self._items[name] = item
        return item

    def get(self, name: str) -> T:
        try:
            return self._items[name]
        except KeyError as exc:
            available = ", ".join(self.names()) or "none"
            raise KeyError(f"unknown {self.kind} '{name}'; available: {available}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))

    def __iter__(self) -> Iterator[tuple[str, T]]:
        return iter(sorted(self._items.items()))


adapters: Registry[type[EnvironmentAdapter]] = Registry("adapter")
agents: Registry[Agent] = Registry("agent")
reporters: Registry[type[Reporter]] = Registry("reporter")
scenarios: Registry[Scenario] = Registry("scenario")


def register_adapter(name: str, adapter: type[EnvironmentAdapter]) -> type[EnvironmentAdapter]:
    return adapters.register(name, adapter)


def get_adapter(name: str) -> type[EnvironmentAdapter]:
    return adapters.get(name)


def register_agent(name: str, agent: Agent) -> Agent:
    return agents.register(name, agent)


def get_agent(name: str) -> Agent:
    return agents.get(name)


def register_reporter(name: str, reporter: type[Reporter]) -> type[Reporter]:
    return reporters.register(name, reporter)


def get_reporter(name: str) -> type[Reporter]:
    return reporters.get(name)


def register_scenario(name: str, scenario: Scenario) -> Scenario:
    return scenarios.register(name, scenario)


def get_scenario(name: str) -> Scenario:
    return scenarios.get(name)
