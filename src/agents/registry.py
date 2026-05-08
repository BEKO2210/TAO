"""Static metadata for all 25 ATLAS agents.

Each agent has a name, layer, prompt-file path, default tickers / data context,
and a starting Darwinian weight. New agents created by the spawning mechanism
also get registered here at runtime.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import PROMPTS_DIR, WEIGHT_START


@dataclass
class AgentSpec:
    name: str
    layer: int                # 1 macro, 2 sector, 3 superinvestor, 4 decision
    prompt_file: Path
    tickers: List[str] = field(default_factory=list)
    description: str = ""
    default_weight: float = WEIGHT_START

    @property
    def slug(self) -> str:
        return self.name


def _p(*parts: str) -> Path:
    return PROMPTS_DIR.joinpath(*parts)


# --- Layer 1: Macro (10) ---------------------------------------------------
MACRO = [
    AgentSpec("central_bank",      1, _p("macro", "central_bank.md"),
              tickers=["TLT", "SHY", "TBT"],
              description="Fed/ECB policy stance & rate trajectory"),
    AgentSpec("geopolitical",      1, _p("macro", "geopolitical.md"),
              tickers=["GLD", "USO", "XAR", "ITA"],
              description="Conflicts, sanctions, regional risk events"),
    AgentSpec("china",             1, _p("macro", "china.md"),
              tickers=["FXI", "MCHI", "KWEB", "ASHR"],
              description="China growth, stimulus, property"),
    AgentSpec("dollar",            1, _p("macro", "dollar.md"),
              tickers=["UUP", "UDN", "FXE", "FXY"],
              description="DXY direction, FX flows"),
    AgentSpec("yield_curve",       1, _p("macro", "yield_curve.md"),
              tickers=["TLT", "IEF", "SHY", "TBT"],
              description="2s10s, real rates, term premium"),
    AgentSpec("commodities",       1, _p("macro", "commodities.md"),
              tickers=["DBC", "GLD", "USO", "DBA", "SLV"],
              description="Oil, gold, copper, agricultural"),
    AgentSpec("volatility",        1, _p("macro", "volatility.md"),
              tickers=["VXX", "UVXY", "SVXY"],
              description="VIX, MOVE, credit spreads, skew"),
    AgentSpec("emerging_markets",  1, _p("macro", "emerging_markets.md"),
              tickers=["EEM", "VWO", "EMB", "EWZ", "INDA"],
              description="EM FX, spreads, flows"),
    AgentSpec("news_sentiment",    1, _p("macro", "news_sentiment.md"),
              tickers=["SPY", "QQQ"],
              description="Headlines, social media, earnings calls"),
    AgentSpec("institutional_flow",1, _p("macro", "institutional_flow.md"),
              tickers=["SPY", "QQQ", "IWM"],
              description="COT, fund flows, 13F positioning"),
]

# --- Layer 2: Sector Desks (7) --------------------------------------------
SECTOR = [
    AgentSpec("semiconductor",       2, _p("sector", "semiconductor.md"),
              tickers=["NVDA", "AMD", "AVGO", "TSM", "ASML", "INTC", "MU", "SMH"]),
    AgentSpec("energy",              2, _p("sector", "energy.md"),
              tickers=["XOM", "CVX", "SLB", "OXY", "COP", "XLE"]),
    AgentSpec("biotech",             2, _p("sector", "biotech.md"),
              tickers=["LLY", "PFE", "MRK", "ABBV", "REGN", "VRTX", "XBI", "IBB"]),
    AgentSpec("consumer",            2, _p("sector", "consumer.md"),
              tickers=["AMZN", "WMT", "COST", "HD", "MCD", "XLY", "XLP"]),
    AgentSpec("industrials",         2, _p("sector", "industrials.md"),
              tickers=["CAT", "DE", "BA", "LMT", "RTX", "GE", "XLI"]),
    AgentSpec("financials",          2, _p("sector", "financials.md"),
              tickers=["JPM", "BAC", "GS", "MS", "WFC", "BLK", "XLF"]),
    AgentSpec("relationship_mapper", 2, _p("sector", "relationship_mapper.md"),
              tickers=[],
              description="Cross-sector supply chains, ownership, analyst links"),
]

# --- Layer 3: Superinvestors (4) ------------------------------------------
SUPER = [
    AgentSpec("druckenmiller",  3, _p("superinvestor", "druckenmiller.md"),
              tickers=[], description="Macro/momentum, asymmetric bets"),
    AgentSpec("aschenbrenner",  3, _p("superinvestor", "aschenbrenner.md"),
              tickers=["NVDA", "AVGO", "TSM", "MSFT", "GOOGL"],
              description="AI capex supercycle"),
    AgentSpec("baker",          3, _p("superinvestor", "baker.md"),
              tickers=[], description="Deep tech / biotech IP moats"),
    AgentSpec("ackman",         3, _p("superinvestor", "ackman.md"),
              tickers=[], description="Quality compounder, FCF, catalyst"),
]

# --- Layer 4: Decision (4) -------------------------------------------------
DECISION = [
    AgentSpec("cro",                  4, _p("decision", "cro.md"),
              description="Adversarial risk officer"),
    AgentSpec("alpha_discovery",      4, _p("decision", "alpha_discovery.md"),
              description="Find names nobody else mentioned"),
    AgentSpec("autonomous_execution", 4, _p("decision", "autonomous_execution.md"),
              description="Convert signals to sized trades"),
    AgentSpec("cio",                  4, _p("decision", "cio.md"),
              description="Final synthesis and portfolio decision"),
]

ALL_AGENTS: List[AgentSpec] = MACRO + SECTOR + SUPER + DECISION


def by_name(name: str) -> Optional[AgentSpec]:
    for a in ALL_AGENTS:
        if a.name == name:
            return a
    return None


def by_layer(layer: int) -> List[AgentSpec]:
    return [a for a in ALL_AGENTS if a.layer == layer]


def names() -> List[str]:
    return [a.name for a in ALL_AGENTS]


def as_dict() -> Dict[str, AgentSpec]:
    return {a.name: a for a in ALL_AGENTS}


def universe_tickers() -> List[str]:
    """Union of all tickers covered by sector desks + superinvestors."""
    out = set()
    for a in ALL_AGENTS:
        for t in a.tickers:
            out.add(t)
    return sorted(out)
