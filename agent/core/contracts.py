"""Typed boundaries around the official Kaggriculture protocol."""

from __future__ import annotations

from typing import Annotated, Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

Scalar: TypeAlias = str | int | float | bool  # noqa: UP040 - Kaggle runs Python 3.11.


class Action(BaseModel):
    """An action accepted by the Kaggriculture environment."""

    model_config = ConfigDict(extra="forbid")
    farmer: Annotated[list[Scalar], Field(default_factory=lambda: ["PASS"])]
    hands: Annotated[list[list[Scalar]], Field(default_factory=list)]
    market: Annotated[list[list[Scalar]], Field(default_factory=list)]

    @classmethod
    def pass_action(cls) -> Action:
        return cls(farmer=["PASS"], hands=[], market=[])


class UnitAction(BaseModel):
    """Immutable representation of one official farmer/hand command."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    command: tuple[Scalar, ...] = ("PASS",)


class MarketOrder(BaseModel):
    """Immutable representation of one official market order."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    command: tuple[Scalar, ...]


class FarmSnapshot(BaseModel):
    """Known public farm fields; unknown official additions are retained."""

    model_config = ConfigDict(frozen=True, extra="allow")
    money: float = 0
    farmer: tuple[int, int] = (0, 0)
    hands: tuple[tuple[int, int], ...] = ()
    tiles: tuple[tuple[Any, ...], ...] = ()
    unlocked_quadrants: tuple[str, ...] = ()


class PrivateSnapshot(BaseModel):
    """Known private state, including individual inventories and the shed."""

    model_config = ConfigDict(frozen=True, extra="allow")
    shed: dict[str, int] = Field(default_factory=dict)
    seeds: dict[str, int] = Field(default_factory=dict)
    inventories: tuple[dict[str, int], ...] = ()


class GameObservation(BaseModel):
    """Immutable normalized shell for every official observation section."""

    model_config = ConfigDict(frozen=True, extra="allow")
    player: int = 0
    day: int = 0
    hour: int = 0
    step: int = 0
    farms: tuple[FarmSnapshot, ...] = ()
    market: dict[str, Any] = Field(default_factory=dict)
    town: dict[str, Any] = Field(default_factory=dict)
    private: PrivateSnapshot = Field(default_factory=PrivateSnapshot)


class Observation(BaseModel):
    """Partial model for the evolving official protocol."""

    model_config = ConfigDict(extra="allow")
    player: int = 0
    day: int = 0
    hour: int = 0
    step: int = 0
    farms: Annotated[list[dict[str, Any]], Field(default_factory=list)]
    market: Annotated[dict[str, Any], Field(default_factory=dict)]
    town: Annotated[dict[str, Any], Field(default_factory=dict)]
    private: Annotated[dict[str, Any], Field(default_factory=dict)]
