"""End-of-day cycle: runs all 25 agents through the 4-layer pipeline.

Layer 1 (Macro) → regime
Layer 2 (Sector) → sector picks (informed by regime)
Layer 3 (Superinvestor) → philosophy-filtered ideas
Layer 4 (CRO + Alpha + Execution + CIO) → final portfolio actions

Each agent call is one Claude completion. Within a layer, agents run
concurrently via ThreadPoolExecutor.
"""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agents import registry, scorecard
from agents.market_data import MarketData
from agents.scorecard import Recommendation
from config.settings import STATE_DIR
from utils import llm
from utils.logging_utils import get_logger

logger = get_logger("eod_cycle")

CYCLE_OUT_DIR = STATE_DIR / "cycles"
CYCLE_OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def load_prompt(spec) -> str:
    """Load the prompt file content for an agent."""
    p = Path(spec.prompt_file)
    if not p.exists():
        logger.warning(f"Prompt file missing for {spec.name}: {p}")
        return f"You are the {spec.name} agent. {spec.description}"
    return p.read_text()


# ---------------------------------------------------------------------------
# Output schema (what we ask each agent to return)
# ---------------------------------------------------------------------------

LAYER1_FORMAT = """
Return JSON with this shape only:
{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "conviction": 0-100,
  "rationale": "1-2 sentence summary",
  "tickers": [
    {"ticker": "XXX", "direction": "LONG" | "SHORT", "conviction": 0-100, "thesis": "..."}
  ]
}
"""

LAYER2_FORMAT = """
Return JSON only:
{
  "sector_view": "OVERWEIGHT" | "NEUTRAL" | "UNDERWEIGHT",
  "rationale": "1-2 sentences",
  "picks": [
    {"ticker": "XXX", "direction": "LONG" | "SHORT", "conviction": 0-100, "thesis": "..."}
  ]
}
"""

LAYER3_FORMAT = """
Return JSON only:
{
  "philosophy_check": "...",
  "endorsed": [
    {"ticker": "XXX", "direction": "LONG" | "SHORT", "conviction": 0-100, "thesis": "..."}
  ],
  "rejected_tickers": ["YYY"],
  "missing_name": {"ticker": "ZZZ", "direction": "LONG" | "SHORT", "conviction": 0-100, "thesis": "..."}
}
"""

LAYER4_CRO_FORMAT = """
Return JSON only:
{
  "approved": [{"ticker": "XXX", "direction": "LONG" | "SHORT", "conviction": 0-100, "rationale": "..."}],
  "rejected": [{"ticker": "YYY", "reason": "..."}],
  "portfolio_risks": ["..."]
}
"""

LAYER4_CIO_FORMAT = """
Return JSON only:
{
  "market_view": "...",
  "actions": [
    {"ticker": "XXX", "action": "BUY" | "SELL" | "HOLD" | "TRIM" | "ADD",
     "size_pct": 0-10, "rationale": "...", "conviction": 0-100, "direction": "LONG" | "SHORT"}
  ],
  "exposure": {"gross": 0.0-1.5, "net": -1.0-1.0},
  "risk_commentary": "..."
}
"""


# ---------------------------------------------------------------------------
# Single-agent runner
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    agent: str
    layer: int
    output: Optional[Dict[str, Any]]
    error: Optional[str] = None


def _run_agent(spec, context: str, output_format: str) -> AgentResult:
    system = load_prompt(spec) + "\n\n" + output_format
    try:
        data = llm.call_json(user=context, system=system)
        return AgentResult(spec.name, spec.layer, data)
    except Exception as e:
        logger.error(f"Agent {spec.name} failed: {e}")
        return AgentResult(spec.name, spec.layer, None, error=str(e))


def _run_layer(specs, context: str, output_format: str, max_workers: int = 8) -> List[AgentResult]:
    results: List[AgentResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_run_agent, s, context, output_format) for s in specs]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


# ---------------------------------------------------------------------------
# Layer-specific context builders
# ---------------------------------------------------------------------------

def _macro_context(market_data: MarketData) -> str:
    snap = market_data.snapshot([])
    macro = snap.get("macro", {})
    return (
        f"DATE: {date.today().isoformat()}\n"
        f"REGIME: {snap.get('regime')}\n"
        f"MACRO SNAPSHOT:\n{json.dumps(macro, indent=2, default=str)}\n"
    )


def _sector_context(market_data: MarketData, regime: str, macro_summary: str, spec) -> str:
    prices = market_data.prices.get_many(spec.tickers) if spec.tickers else {}
    return (
        f"DATE: {date.today().isoformat()}\n"
        f"REGIME: {regime}\n\n"
        f"MACRO SUMMARY:\n{macro_summary}\n\n"
        f"YOUR COVERAGE PRICES:\n{json.dumps(prices, indent=2, default=str)}\n"
    )


def _super_context(regime: str, macro_summary: str, sector_picks: List[Dict]) -> str:
    return (
        f"DATE: {date.today().isoformat()}\n"
        f"REGIME: {regime}\n\n"
        f"MACRO SUMMARY:\n{macro_summary}\n\n"
        f"SECTOR DESK PICKS:\n{json.dumps(sector_picks, indent=2, default=str)}\n"
    )


def _decision_context(regime: str, macro_summary: str,
                      sector_picks: List[Dict], super_endorsed: List[Dict],
                      weights: Dict[str, float]) -> str:
    return (
        f"DATE: {date.today().isoformat()}\n"
        f"REGIME: {regime}\n\n"
        f"MACRO SUMMARY:\n{macro_summary}\n\n"
        f"SECTOR PICKS:\n{json.dumps(sector_picks, indent=2, default=str)}\n\n"
        f"SUPERINVESTOR ENDORSED:\n{json.dumps(super_endorsed, indent=2, default=str)}\n\n"
        f"DARWINIAN WEIGHTS:\n{json.dumps(weights, indent=2, default=str)}\n"
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _summarise_macro(layer1: List[AgentResult], weights: Dict[str, float]) -> Dict[str, Any]:
    """Weighted aggregation of macro signals into a single regime call."""
    bull = bear = neut = 0.0
    rationales = []
    for r in layer1:
        if not r.output:
            continue
        w = weights.get(r.agent, 1.0)
        signal = (r.output.get("signal") or "NEUTRAL").upper()
        conv = float(r.output.get("conviction", 50))
        weighted = w * conv
        if signal == "BULLISH":
            bull += weighted
        elif signal == "BEARISH":
            bear += weighted
        else:
            neut += weighted
        rationales.append(f"{r.agent} ({signal}, {conv:.0f}): {r.output.get('rationale', '')}")
    total = bull + bear + neut or 1
    if bull / total > 0.5:
        regime = "RISK_ON"
    elif bear / total > 0.5:
        regime = "RISK_OFF"
    else:
        regime = "NEUTRAL"
    return {
        "regime": regime,
        "bull_score": round(bull, 1),
        "bear_score": round(bear, 1),
        "neutral_score": round(neut, 1),
        "rationales": rationales,
    }


def _flatten_sector_picks(layer2: List[AgentResult]) -> List[Dict]:
    out = []
    for r in layer2:
        if not r.output:
            continue
        for pick in r.output.get("picks", []):
            pick = dict(pick)
            pick["source_agent"] = r.agent
            pick["sector_view"] = r.output.get("sector_view")
            out.append(pick)
    return out


def _flatten_super_endorsed(layer3: List[AgentResult]) -> List[Dict]:
    out = []
    for r in layer3:
        if not r.output:
            continue
        for e in r.output.get("endorsed", []):
            e = dict(e)
            e["source_agent"] = r.agent
            out.append(e)
        m = r.output.get("missing_name")
        if m and m.get("ticker"):
            m = dict(m)
            m["source_agent"] = r.agent
            m["from_missing"] = True
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_cycle(
    market_data: Optional[MarketData] = None,
    cycle_date: Optional[date] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Run one full daily debate. Returns a dict with all artefacts."""
    market_data = market_data or MarketData()
    cycle_date = cycle_date or date.today()
    cycle_id = f"{cycle_date.isoformat()}_{uuid.uuid4().hex[:6]}"
    logger.info(f"=== CYCLE {cycle_id} ===")

    # Initialise weights for any new agents
    weights = scorecard.init_weights(registry.names())

    # ---- Layer 1: Macro --------------------------------------------------
    macro_ctx = _macro_context(market_data)
    layer1 = _run_layer(registry.MACRO, macro_ctx, LAYER1_FORMAT)
    macro_summary = _summarise_macro(layer1, weights)
    regime = macro_summary["regime"]
    logger.info(f"Layer 1 complete. Regime: {regime}")

    # ---- Layer 2: Sector Desks ------------------------------------------
    macro_text = json.dumps(macro_summary, indent=2)
    sector_results: List[AgentResult] = []
    with ThreadPoolExecutor(max_workers=7) as ex:
        futures = {
            ex.submit(_run_agent, spec,
                      _sector_context(market_data, regime, macro_text, spec),
                      LAYER2_FORMAT): spec
            for spec in registry.SECTOR
        }
        for fut in as_completed(futures):
            sector_results.append(fut.result())
    sector_picks = _flatten_sector_picks(sector_results)
    logger.info(f"Layer 2 complete. {len(sector_picks)} sector picks.")

    # ---- Layer 3: Superinvestors ----------------------------------------
    super_ctx = _super_context(regime, macro_text, sector_picks)
    layer3 = _run_layer(registry.SUPER, super_ctx, LAYER3_FORMAT)
    super_endorsed = _flatten_super_endorsed(layer3)
    logger.info(f"Layer 3 complete. {len(super_endorsed)} endorsed names.")

    # ---- Layer 4: CRO + Alpha + Execution + CIO -------------------------
    decision_ctx = _decision_context(regime, macro_text, sector_picks, super_endorsed, weights)

    cro_spec = registry.by_name("cro")
    alpha_spec = registry.by_name("alpha_discovery")
    exec_spec = registry.by_name("autonomous_execution")
    cio_spec = registry.by_name("cio")

    cro_result = _run_agent(cro_spec, decision_ctx, LAYER4_CRO_FORMAT)
    alpha_result = _run_agent(alpha_spec, decision_ctx, LAYER3_FORMAT)

    # CIO sees CRO output too
    cio_ctx = decision_ctx + "\n\nCRO REVIEW:\n" + json.dumps(
        cro_result.output or {}, indent=2, default=str
    ) + "\n\nALPHA DISCOVERY:\n" + json.dumps(
        alpha_result.output or {}, indent=2, default=str
    )
    cio_result = _run_agent(cio_spec, cio_ctx, LAYER4_CIO_FORMAT)
    exec_result = _run_agent(exec_spec, cio_ctx, LAYER4_CIO_FORMAT)

    portfolio_actions = (cio_result.output or {}).get("actions", [])
    logger.info(f"Layer 4 complete. {len(portfolio_actions)} portfolio actions.")

    # ---- Log every recommendation for scorecard tracking ---------------
    if persist:
        for layer_results, base in (
            (layer1, "layer1"),
            (sector_results, "layer2"),
            (layer3, "layer3"),
        ):
            for r in layer_results:
                if not r.output:
                    continue
                tickers = r.output.get("tickers") or r.output.get("picks") or r.output.get("endorsed") or []
                for t in tickers:
                    ticker = t.get("ticker")
                    if not ticker:
                        continue
                    entry = market_data.close_on(ticker, cycle_date)
                    if entry is None:
                        continue
                    rec = Recommendation(
                        agent=r.agent,
                        ticker=ticker,
                        direction=(t.get("direction") or "LONG").upper(),
                        conviction=float(t.get("conviction", 50)),
                        rationale=t.get("thesis") or t.get("rationale") or "",
                        entry_date=cycle_date.isoformat(),
                        entry_price=entry,
                        cycle_id=cycle_id,
                    )
                    scorecard.log_recommendation(rec)

        # log CIO actions as recommendations of `cio`
        for action in portfolio_actions:
            ticker = action.get("ticker")
            if not ticker:
                continue
            entry = market_data.close_on(ticker, cycle_date)
            if entry is None:
                continue
            scorecard.log_recommendation(Recommendation(
                agent="cio",
                ticker=ticker,
                direction=(action.get("direction") or "LONG").upper(),
                conviction=float(action.get("conviction", 60)),
                rationale=action.get("rationale", ""),
                entry_date=cycle_date.isoformat(),
                entry_price=entry,
                cycle_id=cycle_id,
            ))

    out = {
        "cycle_id": cycle_id,
        "date": cycle_date.isoformat(),
        "regime": regime,
        "macro_summary": macro_summary,
        "layer1": [r.__dict__ for r in layer1],
        "layer2_picks": sector_picks,
        "layer3_endorsed": super_endorsed,
        "cro_review": cro_result.output,
        "alpha_discovery": alpha_result.output,
        "cio_decision": cio_result.output,
        "execution_plan": exec_result.output,
        "weights_at_cycle": weights,
    }
    if persist:
        out_file = CYCLE_OUT_DIR / f"{cycle_id}.json"
        out_file.write_text(json.dumps(out, indent=2, default=str))
        logger.info(f"Cycle saved to {out_file}")
    return out
