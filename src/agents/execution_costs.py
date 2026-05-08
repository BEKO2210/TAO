"""Execution cost model: commission + slippage + half-spread.

All costs are charged on entry AND exit. Defaults are intentionally
conservative — real-world fills tend to be worse than backtests assume.

Tuneable via env or by passing a CostModel instance.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_per_share: float = 0.005  # $/share, IBKR Pro tier
    commission_min_per_trade: float = 1.0
    slippage_bps: float = 5.0   # 0.05% — conservative for liquid US equities
    half_spread_bps: float = 5.0  # 0.05%
    short_borrow_bps_annual: float = 50.0  # 0.5%/year on short notional

    def round_trip_bps(self) -> float:
        """Total transaction cost (entry+exit) in basis points of notional."""
        return 2 * (self.slippage_bps + self.half_spread_bps)

    def trade_cost(self, shares: float, price: float) -> float:
        """One-way cost in dollars for a single fill."""
        notional = abs(shares) * price
        comm = max(self.commission_min_per_trade,
                   abs(shares) * self.commission_per_share)
        slip = notional * (self.slippage_bps + self.half_spread_bps) / 10_000.0
        return comm + slip

    def borrow_cost_per_day(self, notional: float) -> float:
        return notional * (self.short_borrow_bps_annual / 10_000.0) / 252.0


def from_env() -> CostModel:
    return CostModel(
        commission_per_share=float(os.getenv("EXEC_COMMISSION_PER_SHARE", "0.005")),
        commission_min_per_trade=float(os.getenv("EXEC_COMMISSION_MIN", "1.0")),
        slippage_bps=float(os.getenv("EXEC_SLIPPAGE_BPS", "5.0")),
        half_spread_bps=float(os.getenv("EXEC_SPREAD_BPS", "5.0")),
        short_borrow_bps_annual=float(os.getenv("EXEC_BORROW_BPS", "50.0")),
    )


DEFAULT = from_env()


def adjust_entry_price(price: float, direction: str, costs: CostModel = DEFAULT) -> float:
    """Worsen the entry price by half-spread + slippage."""
    bump = price * (costs.slippage_bps + costs.half_spread_bps) / 10_000.0
    return price + bump if direction == "LONG" else price - bump


def adjust_exit_price(price: float, direction: str, costs: CostModel = DEFAULT) -> float:
    """Worsen the exit price."""
    bump = price * (costs.slippage_bps + costs.half_spread_bps) / 10_000.0
    return price - bump if direction == "LONG" else price + bump
