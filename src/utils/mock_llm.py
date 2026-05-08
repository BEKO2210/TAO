"""Mock LLM for cheap testing without API calls.

Produces deterministic, agent-aware synthetic outputs so the full pipeline
(eod_cycle, backtest_loop, scorecard, autoresearch) can run end-to-end
without spending money on Claude.

Activate via env var LLM_MODE=mock or by passing mock=True to llm.call*.

The mock is *not* meant to give realistic alpha — it's meant to exercise
the plumbing. Outputs are seeded by (agent_name, date, ticker) so the same
conditions always produce the same recommendation.
"""
import hashlib
import json
import random
import re
from datetime import date
from typing import Any, Dict, List, Optional

# Pull a stable list of tickers from the registry so we don't invent symbols
# the price client can't resolve.
try:
    from agents.registry import ALL_AGENTS, by_name
except Exception:
    ALL_AGENTS = []
    by_name = lambda _n: None  # noqa: E731


_AGENT_RE = re.compile(r"AGENT[: ]+([a-z_]+)", re.IGNORECASE)


def _seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:12], 16)


def _detect_agent(user: str, system: Optional[str]) -> Optional[str]:
    """Best-effort agent detection from prompt context."""
    text = (system or "") + "\n" + user
    # eod_cycle puts the prompt file content into `system`; prompt files start
    # with `# <Title>`. We can also rely on agent names appearing in the system
    # text. Cheaper: look up which registered prompt-file content is in `system`.
    if system:
        for spec in ALL_AGENTS:
            try:
                head = spec.prompt_file.name
            except Exception:
                continue
            if head in system or f"# {spec.name.replace('_', ' ').title()}" in system:
                return spec.name
            # match by H1 line, case-insensitive
            first_line = system.strip().split("\n", 1)[0].lower()
            if spec.name.replace("_", " ") in first_line or spec.name in first_line:
                return spec.name
    m = _AGENT_RE.search(text)
    if m:
        return m.group(1).lower()
    return None


def _detect_date(text: str) -> str:
    m = re.search(r"DATE[: ]+(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else date.today().isoformat()


# ---------------------------------------------------------------------------
# Layer-specific synthesisers
# ---------------------------------------------------------------------------

def _layer1_output(agent: str, date_str: str) -> Dict[str, Any]:
    rng = random.Random(_seed("L1", agent, date_str))
    signal = rng.choices(["BULLISH", "BEARISH", "NEUTRAL"], weights=[0.4, 0.3, 0.3])[0]
    spec = by_name(agent)
    tickers = spec.tickers if spec and spec.tickers else ["SPY", "QQQ"]
    chosen = rng.sample(tickers, k=min(2, len(tickers)))
    direction = "LONG" if signal == "BULLISH" else "SHORT" if signal == "BEARISH" else "LONG"
    return {
        "signal": signal,
        "conviction": rng.randint(40, 85),
        "rationale": f"[mock] {agent} reads {signal.lower()} on {date_str}",
        "tickers": [
            {"ticker": t, "direction": direction,
             "conviction": rng.randint(40, 80),
             "thesis": f"[mock] {agent} thesis on {t}"}
            for t in chosen
        ],
    }


def _layer2_output(agent: str, date_str: str) -> Dict[str, Any]:
    rng = random.Random(_seed("L2", agent, date_str))
    spec = by_name(agent)
    tickers = spec.tickers if spec and spec.tickers else ["SPY"]
    sector_view = rng.choices(["OVERWEIGHT", "NEUTRAL", "UNDERWEIGHT"],
                              weights=[0.35, 0.4, 0.25])[0]
    n_picks = rng.randint(1, min(3, len(tickers)))
    chosen = rng.sample(tickers, k=n_picks)
    picks = []
    for t in chosen:
        d = "LONG" if sector_view == "OVERWEIGHT" else "SHORT" if sector_view == "UNDERWEIGHT" else rng.choice(["LONG", "SHORT"])
        picks.append({
            "ticker": t,
            "direction": d,
            "conviction": rng.randint(45, 80),
            "thesis": f"[mock] {agent} pick {t}",
        })
    return {
        "sector_view": sector_view,
        "rationale": f"[mock] {agent} {sector_view.lower()} on {date_str}",
        "picks": picks,
    }


def _layer3_output(agent: str, date_str: str) -> Dict[str, Any]:
    rng = random.Random(_seed("L3", agent, date_str))
    pool = ["SPY", "QQQ", "NVDA", "AVGO", "AMZN", "MSFT", "GOOGL", "JPM", "XLE", "GLD"]
    n_endorsed = rng.randint(1, 3)
    endorsed = []
    for t in rng.sample(pool, k=n_endorsed):
        endorsed.append({
            "ticker": t,
            "direction": rng.choice(["LONG", "SHORT"]),
            "conviction": rng.randint(50, 85),
            "thesis": f"[mock] {agent} philosophy fit for {t}",
        })
    missing = rng.choice(pool)
    return {
        "philosophy_check": f"[mock] {agent} review",
        "endorsed": endorsed,
        "rejected_tickers": [],
        "missing_name": {
            "ticker": missing,
            "direction": rng.choice(["LONG", "SHORT"]),
            "conviction": rng.randint(45, 70),
            "thesis": f"[mock] off-radar idea: {missing}",
        },
    }


def _cro_output(date_str: str) -> Dict[str, Any]:
    rng = random.Random(_seed("CRO", date_str))
    pool = ["SPY", "QQQ", "NVDA", "AVGO", "AMZN", "MSFT", "JPM"]
    approved = []
    for t in rng.sample(pool, k=rng.randint(1, 3)):
        approved.append({
            "ticker": t,
            "direction": rng.choice(["LONG", "SHORT"]),
            "conviction": rng.randint(50, 75),
            "rationale": "[mock] CRO approved",
        })
    return {
        "approved": approved,
        "rejected": [],
        "portfolio_risks": ["[mock] generic concentration risk"],
    }


def _cio_output(date_str: str) -> Dict[str, Any]:
    rng = random.Random(_seed("CIO", date_str))
    pool = ["SPY", "QQQ", "NVDA", "AVGO", "AMZN", "MSFT", "GOOGL", "JPM"]
    actions = []
    for t in rng.sample(pool, k=rng.randint(1, 4)):
        action = rng.choices(["BUY", "ADD", "TRIM", "HOLD"], weights=[0.4, 0.2, 0.2, 0.2])[0]
        if action == "HOLD":
            continue
        actions.append({
            "ticker": t,
            "action": action,
            "size_pct": round(rng.uniform(1.0, 5.0), 2),
            "rationale": f"[mock] CIO {action} {t}",
            "conviction": rng.randint(50, 80),
            "direction": rng.choice(["LONG", "SHORT"]),
        })
    return {
        "market_view": f"[mock] view on {date_str}",
        "actions": actions,
        "exposure": {"gross": round(rng.uniform(0.4, 1.0), 2),
                     "net":   round(rng.uniform(-0.2, 0.6), 2)},
        "risk_commentary": "[mock] within limits",
    }


# ---------------------------------------------------------------------------
# Public API mirroring utils.llm
# ---------------------------------------------------------------------------

def call(user: str, system: Optional[str] = None, **_kwargs) -> str:
    """Returns a JSON string suitable for parse_json_blob()."""
    return json.dumps(call_json(user, system))


def call_json(user: str, system: Optional[str] = None, **_kwargs) -> Any:
    text = (system or "") + "\n" + user
    date_str = _detect_date(text)
    agent = _detect_agent(user, system)

    spec = by_name(agent) if agent else None

    # Decision-layer agents have specific output shapes
    if agent == "cro":
        return _cro_output(date_str)
    if agent in ("cio", "autonomous_execution"):
        return _cio_output(date_str)
    if agent == "alpha_discovery":
        return _layer3_output(agent or "alpha_discovery", date_str)

    # Generic by layer
    if spec:
        if spec.layer == 1:
            return _layer1_output(spec.name, date_str)
        if spec.layer == 2:
            return _layer2_output(spec.name, date_str)
        if spec.layer == 3:
            return _layer3_output(spec.name, date_str)

    # Autoresearch / unknown — return a generic modification suggestion
    if "modification_summary" in (system or "").lower() or "new_prompt" in (system or "").lower():
        return {
            "diagnosis": "[mock] no real diagnosis available",
            "modification_summary": "[mock] no-op tweak",
            "new_prompt": user.split("--- CURRENT PROMPT ---", 1)[-1].split("---", 1)[0].strip()
                          or "# mock prompt",
        }

    # Fallback: empty Layer-1-shaped output
    return _layer1_output(agent or "unknown", date_str)


def call_premium(user: str, system: Optional[str] = None, **kwargs):
    return call(user, system=system, **kwargs)
