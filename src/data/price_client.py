"""Price client. Primary: yfinance (free, no key). Falls back gracefully if offline."""
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional

from utils.logging_utils import get_logger

logger = get_logger("price_client")

try:
    import yfinance as yf
except ImportError:
    yf = None


class PriceClient:
    """Read-only price data client."""

    def __init__(self):
        if yf is None:
            logger.warning("yfinance not installed — price calls will return None.")

    @lru_cache(maxsize=512)
    def get_price(self, ticker: str) -> Optional[float]:
        """Latest close price."""
        if yf is None:
            return None
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=True)
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"get_price({ticker}) failed: {e}")
            return None

    def get_history(self, ticker: str, start: date, end: date) -> List[Dict]:
        """Daily OHLCV between [start, end]."""
        if yf is None:
            return []
        try:
            t = yf.Ticker(ticker)
            df = t.history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=True,
            )
            if df.empty:
                return []
            out = []
            for idx, row in df.iterrows():
                out.append({
                    "date": idx.date().isoformat() if hasattr(idx, "date") else str(idx),
                    "open": float(row.get("Open", 0)),
                    "high": float(row.get("High", 0)),
                    "low": float(row.get("Low", 0)),
                    "close": float(row.get("Close", 0)),
                    "volume": float(row.get("Volume", 0)),
                })
            return out
        except Exception as e:
            logger.warning(f"get_history({ticker}) failed: {e}")
            return []

    def get_close_on(self, ticker: str, target: date) -> Optional[float]:
        """Close on a specific date (or last close before that date)."""
        hist = self.get_history(ticker, target - timedelta(days=7), target)
        if not hist:
            return None
        for bar in reversed(hist):
            if bar["date"] <= target.isoformat():
                return bar["close"]
        return None

    def forward_return(self, ticker: str, entry_date: date, days_forward: int) -> Optional[float]:
        """Return between entry_date close and entry_date + N business days close."""
        entry = self.get_close_on(ticker, entry_date)
        if entry is None or entry == 0:
            return None
        # +N calendar days, clamp via history lookup
        exit_target = entry_date + timedelta(days=int(days_forward * 1.6))  # rough biz->calendar
        hist = self.get_history(ticker, entry_date + timedelta(days=1), exit_target)
        if not hist:
            return None
        biz_days = [bar for bar in hist if bar["date"] > entry_date.isoformat()]
        if len(biz_days) < days_forward:
            exit_close = biz_days[-1]["close"] if biz_days else None
        else:
            exit_close = biz_days[days_forward - 1]["close"]
        if exit_close is None or exit_close == 0:
            return None
        return (exit_close - entry) / entry

    def get_many(self, tickers: List[str]) -> Dict[str, Optional[float]]:
        return {t: self.get_price(t) for t in tickers}
