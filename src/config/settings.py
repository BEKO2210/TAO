"""Central configuration. Reads from environment / .env file."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
STATE_DIR = DATA_DIR / "state"
PROMPTS_DIR = ROOT_DIR / "prompts"
LOG_DIR = ROOT_DIR.parent / "logs"

for d in (STATE_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MODEL_PREMIUM = os.getenv("CLAUDE_MODEL_PREMIUM", "claude-opus-4-7")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

FMP_API_KEY = os.getenv("FMP_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

WEIGHT_MIN = 0.3
WEIGHT_MAX = 2.5
WEIGHT_START = 1.0
WEIGHT_UP = 1.05
WEIGHT_DOWN = 0.95

AUTORESEARCH_LOOKBACK_DAYS = 60
AUTORESEARCH_TEST_DAYS = 5
AUTORESEARCH_COOLDOWN_DAYS = 5

INITIAL_PORTFOLIO_VALUE = 1_000_000.0
MAX_POSITION_PCT = 0.10
MAX_GROSS_EXPOSURE = 1.5
MAX_NET_EXPOSURE = 1.0
