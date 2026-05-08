"""Aggregates price + macro data with light cross-validation.

The `triple cross-validation` claim from the README ideally pulls each price from
3 independent sources (FMP, Finnhub, Polygon). Here we use yfinance as a single
truthful source, but expose a structured interface that can be extended to more
providers without touching callers.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import STATE_DIR
from data.macro_client import MacroClient
from data.price_client import PriceClient
from utils.logging_utils import get_logger

logger = get_logger("market_data")

SNAPSHOT_FILE = STATE_DIR / "market_snapshot.json"
HISTORY_CACHE_DIR = STATE_DIR / "price_cache"
HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class MarketData:
    """Single point of entry for both real-time and historical data."""

    def __init__(self):
        self.prices = PriceClient()
        self.macro = MacroClient()

    # --- live snapshot -----------------------------------------------------
    def snapshot(self, tickers: List[str]) -> Dict[str, Any]:
        prices = self.prices.get_many(tickers)
        macro = self.macro.get_macro_snapshot()
        snap = {
            "timestamp": datetime.utcnow().isoformat(),
            "regime": self.macro.regime_label(),
            "macro": macro,
            "prices": prices,
            "missing": [t for t, p in prices.items() if p is None],
        }
        try:
            SNAPSHOT_FILE.write_text(json.dumps(snap, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Could not persist snapshot: {e}")
        return snap

    # --- historical (for backtesting) -------------------------------------
    def cached_history(self, ticker: str, start: date, end: date) -> List[Dict]:
        """Daily OHLCV with on-disk caching keyed by ticker+range."""
        cache_file = HISTORY_CACHE_DIR / f"{ticker}_{start.isoformat()}_{end.isoformat()}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                pass
        hist = self.prices.get_history(ticker, start, end)
        if hist:
            try:
                cache_file.write_text(json.dumps(hist))
            except Exception as e:
                logger.warning(f"Could not cache history: {e}")
        return hist

    def close_on(self, ticker: str, target: date) -> Optional[float]:
        return self.prices.get_close_on(ticker, target)

    def forward_return(self, ticker: str, entry: date, days: int) -> Optional[float]:
        return self.prices.forward_return(ticker, entry, days)

    # --- regime helpers ---------------------------------------------------
    def regime(self) -> str:
        return self.macro.regime_label()

    def historical_macro_for(self, target: date) -> Dict[str, Any]:
        """Best-effort macro snapshot for a historical date.

        For backtesting we approximate by reading VIX / yields close on that day.
        Real macro series (CPI, Fed Funds) need FRED — left None unless wired.
        """
        from data.macro_client import PROXIES  # local import to avoid cycle
        out: Dict[str, Optional[float]] = {}
        for key, ticker in PROXIES.items():
            out[key] = self.close_on(ticker, target)
        ten_year = (out.get("tnx_10y") or 0) / 10 if out.get("tnx_10y") else None
        out["ten_year_yield"] = ten_year
        out["regime"] = self._regime_from(out)
        return out

    @staticmethod
    def _regime_from(macro: Dict[str, Any]) -> str:
        vix = macro.get("vix") or 20.0
        if vix > 30:
            return "RISK_OFF_HIGH_VOL"
        if vix < 15:
            return "RISK_ON_COMPLACENT"
        return "NEUTRAL"
