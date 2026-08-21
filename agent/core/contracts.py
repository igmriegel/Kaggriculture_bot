"""Typed boundaries around the official Kaggriculture protocol."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

type Scalar = str | int | float | bool


class Action(BaseModel):
    """An action accepted by the Kaggriculture environment."""

    model_config = ConfigDict(extra="forbid")
    farmer: Annotated[list[Scalar], Field(default_factory=lambda: ["PASS"])]
    market: Annotated[list[list[Scalar]], Field(default_factory=list)]

    @classmethod
    def pass_action(cls) -> Action:
        return cls(farmer=["PASS"], market=[])


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
