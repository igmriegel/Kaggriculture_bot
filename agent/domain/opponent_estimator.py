"""Opponent state tracking and determinization for market competition."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.core.state import NormalizedState


@dataclass
class OpponentEstimate:
    """Estimated opponent production capacity and market threats."""

    estimated_money: int = 0
    estimated_plants_count: int = 0
    estimated_harvest_ready_count: int = 0
    crop_counts: dict[str, int] = field(default_factory=dict)
    threat_level: str = "LOW"  # LOW, MEDIUM, HIGH


class OpponentEstimator:
    """Infers opponent hidden state from public observations."""

    def estimate(self, state: NormalizedState) -> OpponentEstimate:
        opp_money = state.opponent_money
        opp_tiles = state.opponent_tiles

        plants = [t for t in opp_tiles if t.kind == "PLANT"]
        harvest_ready = [t for t in plants if t.yield_units > 0]

        crop_counts: dict[str, int] = {}
        for t in plants:
            if t.crop:
                crop_counts[t.crop] = crop_counts.get(t.crop, 0) + 1

        threat_level = "LOW"
        if len(harvest_ready) >= 4 or opp_money > state.money * 1.5:
            threat_level = "HIGH"
        elif len(harvest_ready) >= 2 or opp_money > state.money:
            threat_level = "MEDIUM"

        return OpponentEstimate(
            estimated_money=opp_money,
            estimated_plants_count=len(plants),
            estimated_harvest_ready_count=len(harvest_ready),
            crop_counts=crop_counts,
            threat_level=threat_level,
        )
