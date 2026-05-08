"""Scorecard: tracks every agent recommendation, scores it against forward returns,
and updates Darwinian weights daily.

State files (JSON, all under src/data/state/):
    recommendations.json   — append-only log of every recommendation
    agent_weights.json     — current Darwinian weights per agent
    agent_scores.json      — rolling Sharpe and other metrics per agent
    weight_history.json    — daily snapshots of weights for plotting
"""
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import (
    AUTORESEARCH_LOOKBACK_DAYS,
    STATE_DIR,
    WEIGHT_DOWN,
    WEIGHT_MAX,
    WEIGHT_MIN,
    WEIGHT_START,
    WEIGHT_UP,
)
from utils.logging_utils import get_logger

logger = get_logger("scorecard")

REC_FILE = STATE_DIR / "recommendations.json"
WEIGHTS_FILE = STATE_DIR / "agent_weights.json"
SCORES_FILE = STATE_DIR / "agent_scores.json"
WEIGHT_HISTORY_FILE = STATE_DIR / "weight_history.json"


@dataclass
class Recommendation:
    agent: str
    ticker: str
    direction: str          # LONG | SHORT
    conviction: float       # 0..100
    rationale: str
    entry_date: str         # ISO date
    entry_price: float
    forward_returns: Dict[str, Optional[float]] = field(
        default_factory=lambda: {"1d": None, "5d": None, "20d": None}
    )
    scored: bool = False
    cycle_id: Optional[str] = None  # ties to eod_cycle run

    def to_dict(self) -> Dict:
        return asdict(self)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to load {path.name}: {e}")
        return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Recommendation log
# ---------------------------------------------------------------------------

def log_recommendation(rec: Recommendation) -> None:
    recs = _load_json(REC_FILE, [])
    recs.append(rec.to_dict())
    _save_json(REC_FILE, recs)


def all_recommendations() -> List[Dict]:
    return _load_json(REC_FILE, [])


def unscored_recommendations() -> List[Dict]:
    return [r for r in all_recommendations() if not r.get("scored")]


def update_recommendation(idx: int, **fields) -> None:
    recs = all_recommendations()
    if 0 <= idx < len(recs):
        recs[idx].update(fields)
        _save_json(REC_FILE, recs)


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

def load_weights() -> Dict[str, float]:
    return _load_json(WEIGHTS_FILE, {})


def save_weights(weights: Dict[str, float]) -> None:
    _save_json(WEIGHTS_FILE, weights)


def get_weight(agent: str) -> float:
    weights = load_weights()
    return weights.get(agent, WEIGHT_START)


def init_weights(agent_names: List[str]) -> Dict[str, float]:
    weights = load_weights()
    changed = False
    for name in agent_names:
        if name not in weights:
            weights[name] = WEIGHT_START
            changed = True
    if changed:
        save_weights(weights)
    return weights


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_pending(market_data) -> int:
    """Compute forward returns for any unscored recommendations whose entry_date
    is far enough in the past. Returns count scored.
    """
    recs = all_recommendations()
    today = date.today()
    scored_count = 0
    for i, rec in enumerate(recs):
        if rec.get("scored"):
            continue
        try:
            entry_date = date.fromisoformat(rec["entry_date"])
        except Exception:
            continue
        days_elapsed = (today - entry_date).days
        if days_elapsed < 1:
            continue

        ticker = rec["ticker"]
        fr = rec.get("forward_returns", {})
        if days_elapsed >= 1 and fr.get("1d") is None:
            fr["1d"] = market_data.forward_return(ticker, entry_date, 1)
        if days_elapsed >= 5 and fr.get("5d") is None:
            fr["5d"] = market_data.forward_return(ticker, entry_date, 5)
        if days_elapsed >= 20 and fr.get("20d") is None:
            fr["20d"] = market_data.forward_return(ticker, entry_date, 20)

        rec["forward_returns"] = fr
        # mark scored once 5d return is known
        if fr.get("5d") is not None:
            rec["scored"] = True
            scored_count += 1
    _save_json(REC_FILE, recs)
    return scored_count


# ---------------------------------------------------------------------------
# Sharpe + per-agent metrics
# ---------------------------------------------------------------------------

def _signed_return(rec: Dict, horizon: str = "5d") -> Optional[float]:
    fr = rec.get("forward_returns", {}).get(horizon)
    if fr is None:
        return None
    direction = (rec.get("direction") or "LONG").upper()
    conviction = float(rec.get("conviction", 50)) / 100.0
    sign = 1.0 if direction == "LONG" else -1.0
    return sign * conviction * fr


def agent_sharpe(agent: str, lookback_days: int = AUTORESEARCH_LOOKBACK_DAYS,
                 horizon: str = "5d") -> float:
    today = date.today()
    cutoff = today.toordinal() - lookback_days
    returns: List[float] = []
    for rec in all_recommendations():
        if rec.get("agent") != agent:
            continue
        try:
            ed = date.fromisoformat(rec["entry_date"]).toordinal()
        except Exception:
            continue
        if ed < cutoff:
            continue
        r = _signed_return(rec, horizon=horizon)
        if r is not None:
            returns.append(r)
    if len(returns) < 3:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)
    sd = math.sqrt(var) if var > 0 else 1e-9
    return (mean / sd) * math.sqrt(252) if sd else 0.0


def agent_hit_rate(agent: str, lookback_days: int = AUTORESEARCH_LOOKBACK_DAYS,
                   horizon: str = "5d") -> float:
    today = date.today()
    cutoff = today.toordinal() - lookback_days
    hits = total = 0
    for rec in all_recommendations():
        if rec.get("agent") != agent:
            continue
        try:
            ed = date.fromisoformat(rec["entry_date"]).toordinal()
        except Exception:
            continue
        if ed < cutoff:
            continue
        fr = rec.get("forward_returns", {}).get(horizon)
        if fr is None:
            continue
        direction = (rec.get("direction") or "LONG").upper()
        if direction == "LONG" and fr > 0:
            hits += 1
        elif direction == "SHORT" and fr < 0:
            hits += 1
        total += 1
    return hits / total if total else 0.0


def all_agent_scores(agent_names: List[str]) -> Dict[str, Dict[str, float]]:
    out = {}
    for name in agent_names:
        out[name] = {
            "sharpe": agent_sharpe(name),
            "hit_rate": agent_hit_rate(name),
            "weight": get_weight(name),
        }
    _save_json(SCORES_FILE, {"updated": datetime.utcnow().isoformat(), "agents": out})
    return out


# ---------------------------------------------------------------------------
# Darwinian weight update
# ---------------------------------------------------------------------------

def update_darwinian_weights(agent_names: List[str]) -> Dict[str, float]:
    """Top-quartile agents get *1.05, bottom-quartile *0.95. Capped to [0.3, 2.5]."""
    scores = {n: agent_sharpe(n) for n in agent_names}
    sorted_agents = sorted(scores.items(), key=lambda kv: kv[1])
    n = len(sorted_agents)
    if n == 0:
        return {}
    q = max(1, n // 4)
    bottom = {a for a, _ in sorted_agents[:q]}
    top = {a for a, _ in sorted_agents[-q:]}

    weights = load_weights()
    for name in agent_names:
        w = weights.get(name, WEIGHT_START)
        if name in top:
            w = min(WEIGHT_MAX, w * WEIGHT_UP)
        elif name in bottom:
            w = max(WEIGHT_MIN, w * WEIGHT_DOWN)
        weights[name] = round(w, 4)
    save_weights(weights)

    # snapshot history
    history = _load_json(WEIGHT_HISTORY_FILE, [])
    history.append({"date": date.today().isoformat(), "weights": weights})
    history = history[-365:]
    _save_json(WEIGHT_HISTORY_FILE, history)

    logger.info(f"Updated Darwinian weights. Top: {sorted(top)}, Bottom: {sorted(bottom)}")
    return weights


def lowest_sharpe_agent(agent_names: List[str], min_recs: int = 5) -> Optional[str]:
    """Pick the agent with the worst Sharpe (with at least `min_recs` recommendations)."""
    counts: Dict[str, int] = {n: 0 for n in agent_names}
    for rec in all_recommendations():
        a = rec.get("agent")
        if a in counts and rec.get("scored"):
            counts[a] += 1
    eligible = [a for a, c in counts.items() if c >= min_recs]
    if not eligible:
        return None
    sharpes = {a: agent_sharpe(a) for a in eligible}
    return min(sharpes, key=sharpes.get)
