"""Protocols expected from an environment adapter."""

from typing import Any, Protocol


class EnvironmentAdapter(Protocol):
    def reset(
        self, seed: int | None = None, configuration: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    def step(self, action: dict[str, Any]) -> dict[str, Any]: ...

    def finished(self) -> bool: ...

    def result(self) -> Any: ...
