"""Main training/backtest loop.

Each iteration = one trading day:
  1. Score forward returns of any pending recommendations
  2. Run the eod_cycle (all 25 agents)
  3. Update Darwinian weights
  4. Run one autoresearch iteration (review + maybe start)
  5. Mark portfolio P&L based on CIO actions
  6. Persist daily state

For a backtest, supply --start and --end and the loop will iterate over
business days in that range (using historical price data via yfinance).
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import eod_cycle, registry, scorecard
from agents.autoresearch import run_one_iteration as autoresearch_iter
from agents.market_data import MarketData
from config.settings import (
    INITIAL_PORTFOLIO_VALUE,
    MAX_GROSS_EXPOSURE,
    MAX_POSITION_PCT,
    ROOT_DIR,
    STATE_DIR,
)
from utils.logging_utils import get_logger

logger = get_logger("backtest")

PORTFOLIO_FILE = STATE_DIR / "portfolio.json"
TRAJECTORY_FILE = STATE_DIR / "portfolio_trajectory.json"
RUN_LOG_FILE = STATE_DIR / "backtest_run_log.json"

REPO_ROOT = ROOT_DIR.parent  # src/.. = repo root


# ---------------------------------------------------------------------------
# Portfolio state
# ---------------------------------------------------------------------------

@dataclass
class Position:
    ticker: str
    direction: str        # LONG | SHORT
    shares: float
    entry_price: float
    entry_date: str

    def market_value(self, price: float) -> float:
        sign = 1 if self.direction == "LONG" else -1
        return sign * self.shares * price


@dataclass
class Portfolio:
    cash: float = INITIAL_PORTFOLIO_VALUE
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "cash": self.cash,
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "realized_pnl": self.realized_pnl,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Portfolio":
        p = cls(cash=data.get("cash", INITIAL_PORTFOLIO_VALUE),
                realized_pnl=data.get("realized_pnl", 0.0))
        for ticker, pos in (data.get("positions") or {}).items():
            p.positions[ticker] = Position(**pos)
        return p


def load_portfolio() -> Portfolio:
    if PORTFOLIO_FILE.exists():
        try:
            return Portfolio.from_dict(json.loads(PORTFOLIO_FILE.read_text()))
        except Exception as e:
            logger.warning(f"Could not load portfolio, resetting: {e}")
    return Portfolio()


def save_portfolio(p: Portfolio) -> None:
    PORTFOLIO_FILE.write_text(json.dumps(p.to_dict(), indent=2, default=str))


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------

def _portfolio_value(p: Portfolio, market: MarketData, on_date: date) -> float:
    total = p.cash
    for ticker, pos in p.positions.items():
        price = market.close_on(ticker, on_date) or pos.entry_price
        total += pos.market_value(price)
    return total


def execute_actions(p: Portfolio, actions: List[Dict[str, Any]],
                    market: MarketData, on_date: date) -> List[Dict]:
    """Apply CIO actions to the portfolio. Returns list of executed trades."""
    pv = _portfolio_value(p, market, on_date)
    executed = []
    for a in actions:
        ticker = a.get("ticker")
        action = (a.get("action") or "HOLD").upper()
        if not ticker or action == "HOLD":
            continue
        size_pct = min(float(a.get("size_pct", 2.0)), MAX_POSITION_PCT * 100) / 100.0
        target_dollars = pv * size_pct
        price = market.close_on(ticker, on_date)
        if not price or price <= 0:
            continue
        direction = (a.get("direction") or "LONG").upper()
        shares = round(target_dollars / price, 4)

        existing = p.positions.get(ticker)
        if action in ("BUY", "ADD"):
            if existing and existing.direction == direction:
                # average up
                total_cost = existing.shares * existing.entry_price + shares * price
                existing.shares += shares
                existing.entry_price = total_cost / existing.shares if existing.shares else price
            else:
                if existing:
                    p.realized_pnl += (price - existing.entry_price) * existing.shares * (
                        1 if existing.direction == "LONG" else -1
                    )
                p.positions[ticker] = Position(ticker, direction, shares, price, on_date.isoformat())
            p.cash -= shares * price * (1 if direction == "LONG" else -1)
            executed.append({"ticker": ticker, "action": action, "shares": shares, "price": price})
        elif action in ("SELL", "TRIM", "EXIT"):
            if not existing:
                continue
            sell_shares = existing.shares if action == "EXIT" else min(shares, existing.shares)
            sign = 1 if existing.direction == "LONG" else -1
            p.realized_pnl += (price - existing.entry_price) * sell_shares * sign
            p.cash += sell_shares * price * sign
            existing.shares -= sell_shares
            if existing.shares <= 1e-6:
                del p.positions[ticker]
            executed.append({"ticker": ticker, "action": action,
                             "shares": sell_shares, "price": price})
    return executed


def enforce_exposure_limits(p: Portfolio, market: MarketData, on_date: date) -> None:
    pv = _portfolio_value(p, market, on_date) or 1.0
    gross = sum(abs(pos.shares * (market.close_on(pos.ticker, on_date) or pos.entry_price))
                for pos in p.positions.values())
    if gross / pv > MAX_GROSS_EXPOSURE:
        scale = MAX_GROSS_EXPOSURE * pv / gross
        for pos in p.positions.values():
            pos.shares *= scale


# ---------------------------------------------------------------------------
# Single iteration
# ---------------------------------------------------------------------------

def _business_days(start: date, end: date) -> List[date]:
    out = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def run_one_day(cycle_date: date, market: MarketData, portfolio: Portfolio,
                use_autoresearch: bool = True) -> Dict[str, Any]:
    logger.info(f"--- Running iteration for {cycle_date.isoformat()} ---")

    # 1. Score any pending forward returns
    n_scored = scorecard.score_pending(market)
    logger.info(f"Scored {n_scored} pending recommendations.")

    # 2. Run the daily cycle
    cycle = eod_cycle.run_cycle(market_data=market, cycle_date=cycle_date)

    # 3. Update Darwinian weights
    weights = scorecard.update_darwinian_weights(registry.names())

    # 4. Autoresearch
    autores_result = {}
    if use_autoresearch:
        try:
            autores_result = autoresearch_iter(REPO_ROOT)
        except Exception as e:
            logger.warning(f"Autoresearch step skipped: {e}")
            autores_result = {"error": str(e)}

    # 5. Execute CIO actions
    cio = (cycle.get("cio_decision") or {})
    actions = cio.get("actions", [])
    executed = execute_actions(portfolio, actions, market, cycle_date)
    enforce_exposure_limits(portfolio, market, cycle_date)
    save_portfolio(portfolio)

    pv = _portfolio_value(portfolio, market, cycle_date)
    daily_record = {
        "date": cycle_date.isoformat(),
        "regime": cycle.get("regime"),
        "portfolio_value": pv,
        "cash": portfolio.cash,
        "n_positions": len(portfolio.positions),
        "executed": executed,
        "weights_top": dict(sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:5]),
        "autoresearch": autores_result,
        "cycle_id": cycle.get("cycle_id"),
    }
    _append_trajectory(daily_record)
    return daily_record


def _append_trajectory(record: Dict) -> None:
    traj = []
    if TRAJECTORY_FILE.exists():
        try:
            traj = json.loads(TRAJECTORY_FILE.read_text())
        except Exception:
            traj = []
    traj.append(record)
    TRAJECTORY_FILE.write_text(json.dumps(traj, indent=2, default=str))


# ---------------------------------------------------------------------------
# Backtest entry point
# ---------------------------------------------------------------------------

def run_backtest(start: date, end: date, use_autoresearch: bool = True) -> Dict:
    market = MarketData()
    portfolio = load_portfolio()
    days = _business_days(start, end)
    logger.info(f"Backtest: {len(days)} trading days from {start} to {end}")

    summary = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trading_days": len(days),
        "starting_value": INITIAL_PORTFOLIO_VALUE,
        "daily_records": [],
    }
    for d in days:
        try:
            rec = run_one_day(d, market, portfolio, use_autoresearch=use_autoresearch)
            summary["daily_records"].append(rec)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user; saving partial state.")
            break
        except Exception as e:
            logger.error(f"Iteration {d} failed: {e}")
            summary["daily_records"].append({"date": d.isoformat(), "error": str(e)})

    final_pv = _portfolio_value(portfolio, market, days[-1] if days else date.today())
    summary["ending_value"] = final_pv
    summary["total_return_pct"] = (final_pv / INITIAL_PORTFOLIO_VALUE - 1.0) * 100
    summary["completed_at"] = datetime.utcnow().isoformat()
    RUN_LOG_FILE.write_text(json.dumps(summary, indent=2, default=str))
    logger.info(f"Backtest complete. Final value: ${final_pv:,.2f} "
                f"({summary['total_return_pct']:+.2f}%)")
    return summary


def run_live_one_day(use_autoresearch: bool = True) -> Dict:
    market = MarketData()
    portfolio = load_portfolio()
    return run_one_day(date.today(), market, portfolio, use_autoresearch=use_autoresearch)
