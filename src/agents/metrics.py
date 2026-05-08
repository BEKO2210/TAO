"""Performance metrics. Pure-python (no numpy/pandas required)."""
import json
import math
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from config.settings import STATE_DIR
from utils.logging_utils import get_logger

logger = get_logger("metrics")

TRAJECTORY_FILE = STATE_DIR / "portfolio_trajectory.json"
BENCHMARK_FILE = STATE_DIR / "benchmark_trajectory.json"
METRICS_FILE = STATE_DIR / "metrics.json"

TRADING_DAYS_YEAR = 252


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def returns_from_equity(equity: Sequence[float]) -> List[float]:
    out = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev:
            out.append(equity[i] / prev - 1.0)
    return out


def annualised_return(equity: Sequence[float], n_days: Optional[int] = None) -> float:
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    days = n_days if n_days is not None else len(equity) - 1
    if days <= 0:
        return 0.0
    total = equity[-1] / equity[0]
    return total ** (TRADING_DAYS_YEAR / days) - 1.0


def sharpe(daily_returns: Sequence[float], rf_annual: float = 0.045) -> float:
    if len(daily_returns) < 2:
        return 0.0
    rf_daily = rf_annual / TRADING_DAYS_YEAR
    excess = [r - rf_daily for r in daily_returns]
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    sd = math.sqrt(var) if var > 0 else 1e-9
    return (mean / sd) * math.sqrt(TRADING_DAYS_YEAR)


def sortino(daily_returns: Sequence[float], rf_annual: float = 0.045) -> float:
    if len(daily_returns) < 2:
        return 0.0
    rf_daily = rf_annual / TRADING_DAYS_YEAR
    excess = [r - rf_daily for r in daily_returns]
    downside = [min(0, x) for x in excess]
    if not any(d < 0 for d in downside):
        return 0.0
    dd_var = sum(d * d for d in downside) / len(downside)
    dd = math.sqrt(dd_var) if dd_var > 0 else 1e-9
    mean = sum(excess) / len(excess)
    return (mean / dd) * math.sqrt(TRADING_DAYS_YEAR)


def max_drawdown(equity: Sequence[float]) -> Dict[str, float]:
    if not equity:
        return {"max_dd_pct": 0.0, "peak_idx": 0, "trough_idx": 0}
    peak = equity[0]
    peak_idx = 0
    max_dd = 0.0
    trough_idx = 0
    cur_peak_idx = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
            cur_peak_idx = i
        dd = (v / peak - 1.0) if peak else 0.0
        if dd < max_dd:
            max_dd = dd
            peak_idx = cur_peak_idx
            trough_idx = i
    return {
        "max_dd_pct": max_dd * 100,
        "peak_idx": peak_idx,
        "trough_idx": trough_idx,
    }


def calmar(equity: Sequence[float]) -> float:
    if len(equity) < 2:
        return 0.0
    ann = annualised_return(equity)
    dd = abs(max_drawdown(equity)["max_dd_pct"]) / 100
    return ann / dd if dd > 0 else 0.0


def win_rate(daily_returns: Sequence[float]) -> float:
    if not daily_returns:
        return 0.0
    wins = sum(1 for r in daily_returns if r > 0)
    return wins / len(daily_returns)


def volatility_annual(daily_returns: Sequence[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    m = sum(daily_returns) / len(daily_returns)
    var = sum((r - m) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS_YEAR)


# ---------------------------------------------------------------------------
# Strategy vs benchmark comparison
# ---------------------------------------------------------------------------

def beta_alpha(strategy_returns: Sequence[float],
               benchmark_returns: Sequence[float]) -> Dict[str, float]:
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 2:
        return {"beta": 0.0, "alpha_annual_pct": 0.0,
                "tracking_error": 0.0, "info_ratio": 0.0}
    s = strategy_returns[:n]
    b = benchmark_returns[:n]
    mean_s, mean_b = sum(s) / n, sum(b) / n
    cov = sum((s[i] - mean_s) * (b[i] - mean_b) for i in range(n)) / (n - 1)
    var_b = sum((b[i] - mean_b) ** 2 for i in range(n)) / (n - 1) or 1e-9
    beta = cov / var_b
    alpha_daily = mean_s - beta * mean_b
    alpha_annual = alpha_daily * TRADING_DAYS_YEAR
    diffs = [s[i] - b[i] for i in range(n)]
    md = sum(diffs) / n
    te_var = sum((d - md) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
    te = math.sqrt(te_var) * math.sqrt(TRADING_DAYS_YEAR)
    ir = (md * TRADING_DAYS_YEAR / te) if te > 0 else 0.0
    return {
        "beta": round(beta, 4),
        "alpha_annual_pct": round(alpha_annual * 100, 3),
        "tracking_error": round(te, 4),
        "info_ratio": round(ir, 3),
    }


# ---------------------------------------------------------------------------
# Top-level summary from on-disk trajectory files
# ---------------------------------------------------------------------------

def _load_equity_from_trajectory(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Could not load {path.name}: {e}")
        return []


def summarise(persist: bool = True) -> Dict:
    """Build a metrics summary from portfolio_trajectory.json + benchmark_trajectory.json."""
    strat = _load_equity_from_trajectory(TRAJECTORY_FILE)
    bench = _load_equity_from_trajectory(BENCHMARK_FILE)

    strat_eq = [r.get("portfolio_value") for r in strat if r.get("portfolio_value") is not None]
    bench_eq = [r.get("value") for r in bench if r.get("value") is not None]

    strat_rets = returns_from_equity(strat_eq)
    bench_rets = returns_from_equity(bench_eq)

    summary = {
        "as_of": date.today().isoformat(),
        "strategy": {
            "n_days": len(strat_eq),
            "starting_value": strat_eq[0] if strat_eq else None,
            "ending_value": strat_eq[-1] if strat_eq else None,
            "total_return_pct": (strat_eq[-1] / strat_eq[0] - 1) * 100 if len(strat_eq) >= 2 and strat_eq[0] else None,
            "annualised_return_pct": annualised_return(strat_eq) * 100 if len(strat_eq) >= 2 else None,
            "sharpe": round(sharpe(strat_rets), 3),
            "sortino": round(sortino(strat_rets), 3),
            "max_drawdown_pct": round(max_drawdown(strat_eq)["max_dd_pct"], 2),
            "calmar": round(calmar(strat_eq), 3),
            "volatility_annual_pct": round(volatility_annual(strat_rets) * 100, 2),
            "win_rate_pct": round(win_rate(strat_rets) * 100, 1),
        },
        "benchmark_spy": {
            "n_days": len(bench_eq),
            "starting_value": bench_eq[0] if bench_eq else None,
            "ending_value": bench_eq[-1] if bench_eq else None,
            "total_return_pct": (bench_eq[-1] / bench_eq[0] - 1) * 100 if len(bench_eq) >= 2 and bench_eq[0] else None,
            "annualised_return_pct": annualised_return(bench_eq) * 100 if len(bench_eq) >= 2 else None,
            "sharpe": round(sharpe(bench_rets), 3),
            "max_drawdown_pct": round(max_drawdown(bench_eq)["max_dd_pct"], 2),
        },
    }

    if strat_rets and bench_rets:
        summary["vs_benchmark"] = beta_alpha(strat_rets, bench_rets)

    if persist:
        METRICS_FILE.write_text(json.dumps(summary, indent=2, default=str))
    return summary


def format_summary(summary: Dict) -> str:
    s = summary.get("strategy", {}) or {}
    b = summary.get("benchmark_spy", {}) or {}
    vs = summary.get("vs_benchmark", {}) or {}
    fmt_pct = lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) else "n/a"
    fmt_num = lambda v: f"{v:.3f}" if isinstance(v, (int, float)) else "n/a"

    lines = [
        f"As of {summary.get('as_of')}",
        f"Days: {s.get('n_days')} | Bench: {b.get('n_days')}",
        "",
        f"{'':30}{'Strategy':>14}{'SPY':>14}",
        f"{'Total return':30}{fmt_pct(s.get('total_return_pct')):>14}{fmt_pct(b.get('total_return_pct')):>14}",
        f"{'Annualised return':30}{fmt_pct(s.get('annualised_return_pct')):>14}{fmt_pct(b.get('annualised_return_pct')):>14}",
        f"{'Sharpe':30}{fmt_num(s.get('sharpe')):>14}{fmt_num(b.get('sharpe')):>14}",
        f"{'Max drawdown':30}{fmt_pct(s.get('max_drawdown_pct')):>14}{fmt_pct(b.get('max_drawdown_pct')):>14}",
        f"{'Sortino':30}{fmt_num(s.get('sortino')):>14}",
        f"{'Calmar':30}{fmt_num(s.get('calmar')):>14}",
        f"{'Volatility (ann.)':30}{fmt_pct(s.get('volatility_annual_pct')):>14}",
        f"{'Win rate':30}{fmt_pct(s.get('win_rate_pct')):>14}",
    ]
    if vs:
        lines += [
            "",
            f"{'Beta to SPY':30}{fmt_num(vs.get('beta')):>14}",
            f"{'Alpha (ann.)':30}{fmt_pct(vs.get('alpha_annual_pct')):>14}",
            f"{'Tracking error':30}{fmt_num(vs.get('tracking_error')):>14}",
            f"{'Info ratio':30}{fmt_num(vs.get('info_ratio')):>14}",
        ]
    return "\n".join(lines)
