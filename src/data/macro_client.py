"""Macro data client. Pulls VIX, yields, FX, commodities via yfinance proxies."""
from functools import lru_cache
from typing import Any, Dict, Optional

from utils.logging_utils import get_logger

logger = get_logger("macro_client")

try:
    import yfinance as yf
except ImportError:
    yf = None


# Map of macro indicator -> yfinance ticker proxy
PROXIES = {
    "vix": "^VIX",
    "move": "^MOVE",
    "tnx_10y": "^TNX",      # 10Y yield * 10
    "fvx_5y": "^FVX",
    "irx_3m": "^IRX",       # 13-week T-bill
    "tyx_30y": "^TYX",
    "dxy": "DX-Y.NYB",
    "gold": "GC=F",
    "oil": "CL=F",
    "copper": "HG=F",
    "spy": "SPY",
    "qqq": "QQQ",
    "tlt": "TLT",
    "hyg": "HYG",
    "uup": "UUP",
}


class MacroClient:
    """Read macro indicators."""

    def __init__(self):
        if yf is None:
            logger.warning("yfinance not installed — macro calls will return None.")

    @lru_cache(maxsize=64)
    def _last_close(self, ticker: str) -> Optional[float]:
        if yf is None:
            return None
        try:
            df = yf.Ticker(ticker).history(period="5d")
            if df.empty:
                return None
            return float(df["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"macro {ticker} fetch failed: {e}")
            return None

    def get(self, key: str) -> Optional[float]:
        ticker = PROXIES.get(key.lower())
        if not ticker:
            logger.warning(f"Unknown macro key: {key}")
            return None
        return self._last_close(ticker)

    def get_macro_snapshot(self) -> Dict[str, Any]:
        """Returns a macro snapshot dict shaped like ATLAS expects."""
        vix = self.get("vix")
        tnx = self.get("tnx_10y")
        fvx = self.get("fvx_5y")
        irx = self.get("irx_3m")
        tyx = self.get("tyx_30y")
        dxy = self.get("dxy")
        gold = self.get("gold")
        oil = self.get("oil")
        copper = self.get("copper")
        ten_year = (tnx / 10.0) if tnx else None
        two_year = None  # not on yfinance directly; approximated
        if fvx and irx:
            two_year = (fvx + irx) / 20.0  # rough proxy
        yc = (ten_year - two_year) * 100 if (ten_year and two_year) else None
        return {
            "vix": vix,
            "ten_year_yield": ten_year,
            "five_year_yield": (fvx / 10.0) if fvx else None,
            "three_month_yield": (irx / 10.0) if irx else None,
            "thirty_year_yield": (tyx / 10.0) if tyx else None,
            "yield_curve_10y_2y": yc,
            "dxy": dxy,
            "gold": gold,
            "oil": oil,
            "copper": copper,
            "fed_funds_rate": None,  # requires FRED — leave None unless wired
            "m2_yoy_change": None,
            "cpi_yoy": None,
            "unemployment_rate": None,
        }

    def regime_label(self) -> str:
        snap = self.get_macro_snapshot()
        vix = snap.get("vix") or 20.0
        yc = snap.get("yield_curve_10y_2y") or 0.0
        if vix > 30:
            return "RISK_OFF_HIGH_VOL"
        if vix > 20 and yc < 0:
            return "RISK_OFF_INVERSION"
        if vix < 15:
            return "RISK_ON_COMPLACENT"
        return "NEUTRAL"
