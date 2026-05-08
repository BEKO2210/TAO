"""CLI entry point.

Usage:
    python src/cli.py snapshot                       # show current macro+price snapshot
    python src/cli.py cycle                          # run one EOD cycle (live)
    python src/cli.py backtest 2024-09-01 2024-09-15 # backtest range
    python src/cli.py score                          # update forward returns + Sharpes
    python src/cli.py weights                        # show current Darwinian weights
    python src/cli.py autoresearch                   # run one autoresearch iteration
    python src/cli.py status                         # summary of state
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import autoresearch, backtest_loop, eod_cycle, registry, scorecard
from agents.market_data import MarketData
from config.settings import ROOT_DIR
from utils.logging_utils import get_logger

logger = get_logger("cli")


def cmd_snapshot(_args):
    md = MarketData()
    snap = md.snapshot(registry.universe_tickers())
    print(json.dumps(snap, indent=2, default=str))


def cmd_cycle(_args):
    out = eod_cycle.run_cycle()
    print(json.dumps({k: v for k, v in out.items() if k != "layer1"}, indent=2, default=str))


def cmd_backtest(args):
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    summary = backtest_loop.run_backtest(start, end, use_autoresearch=not args.no_autoresearch)
    print(json.dumps(
        {k: v for k, v in summary.items() if k != "daily_records"},
        indent=2, default=str
    ))


def cmd_score(_args):
    md = MarketData()
    n = scorecard.score_pending(md)
    print(f"Scored {n} recommendations.")
    scores = scorecard.all_agent_scores(registry.names())
    print(json.dumps(scores, indent=2, default=str))


def cmd_weights(_args):
    weights = scorecard.init_weights(registry.names())
    print(json.dumps(weights, indent=2, default=str))


def cmd_autoresearch(_args):
    repo_root = ROOT_DIR.parent
    res = autoresearch.run_one_iteration(repo_root)
    print(json.dumps(res, indent=2, default=str))


def cmd_status(_args):
    weights = scorecard.load_weights()
    recs = scorecard.all_recommendations()
    print(f"Agents registered: {len(registry.names())}")
    print(f"Recommendations logged: {len(recs)}")
    print(f"Scored: {sum(1 for r in recs if r.get('scored'))}")
    print(f"Weights min/max: {min(weights.values(), default=0):.2f} / "
          f"{max(weights.values(), default=0):.2f}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atlas")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("snapshot")
    sp.add_parser("cycle")
    bt = sp.add_parser("backtest")
    bt.add_argument("start"); bt.add_argument("end")
    bt.add_argument("--no-autoresearch", action="store_true")
    sp.add_parser("score")
    sp.add_parser("weights")
    sp.add_parser("autoresearch")
    sp.add_parser("status")
    return p


HANDLERS = {
    "snapshot": cmd_snapshot,
    "cycle": cmd_cycle,
    "backtest": cmd_backtest,
    "score": cmd_score,
    "weights": cmd_weights,
    "autoresearch": cmd_autoresearch,
    "status": cmd_status,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    HANDLERS[args.cmd](args)


if __name__ == "__main__":
    main()
