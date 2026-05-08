"""CLI entry point.

Usage:
    python src/cli.py snapshot                       # macro+price snapshot
    python src/cli.py cycle [--mock]                 # one EOD cycle
    python src/cli.py backtest 2024-09-01 2024-09-15 [--mock] [--no-autoresearch] [--no-reset]
    python src/cli.py score                          # update forward returns + Sharpes
    python src/cli.py weights                        # show current Darwinian weights
    python src/cli.py autoresearch [--mock]          # one autoresearch iteration
    python src/cli.py metrics                        # performance summary
    python src/cli.py reset                          # clear portfolio + trajectory
    python src/cli.py status                         # summary of state
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import autoresearch, backtest_loop, eod_cycle, metrics, registry, scorecard
from agents.market_data import MarketData
from config.settings import ROOT_DIR
from utils import llm
from utils.logging_utils import get_logger

logger = get_logger("cli")


def _maybe_enable_mock(args) -> None:
    if getattr(args, "mock", False):
        llm.set_mock(True)
        logger.info("LLM mock mode enabled — no API calls will be made.")


def cmd_snapshot(_args):
    md = MarketData()
    snap = md.snapshot(registry.universe_tickers())
    print(json.dumps(snap, indent=2, default=str))


def cmd_cycle(args):
    _maybe_enable_mock(args)
    out = eod_cycle.run_cycle()
    print(json.dumps({k: v for k, v in out.items() if k != "layer1"}, indent=2, default=str))


def cmd_backtest(args):
    _maybe_enable_mock(args)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    summary = backtest_loop.run_backtest(
        start, end,
        use_autoresearch=not args.no_autoresearch,
        reset=not args.no_reset,
    )
    print(json.dumps(
        {k: v for k, v in summary.items() if k != "daily_records"},
        indent=2, default=str
    ))
    print()
    print(metrics.format_summary(summary.get("metrics", {})))


def cmd_metrics(_args):
    summary = metrics.summarise()
    print(metrics.format_summary(summary))


def cmd_reset(_args):
    backtest_loop.reset_state()
    print("State reset.")


def cmd_score(_args):
    md = MarketData()
    n = scorecard.score_pending(md)
    print(f"Scored {n} recommendations.")
    scores = scorecard.all_agent_scores(registry.names())
    print(json.dumps(scores, indent=2, default=str))


def cmd_weights(_args):
    weights = scorecard.init_weights(registry.names())
    print(json.dumps(weights, indent=2, default=str))


def cmd_autoresearch(args):
    _maybe_enable_mock(args)
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
    cy = sp.add_parser("cycle")
    cy.add_argument("--mock", action="store_true",
                    help="Use deterministic mock LLM (no API calls).")
    bt = sp.add_parser("backtest")
    bt.add_argument("start"); bt.add_argument("end")
    bt.add_argument("--no-autoresearch", action="store_true")
    bt.add_argument("--no-reset", action="store_true",
                    help="Don't clear state before starting (resume).")
    bt.add_argument("--mock", action="store_true",
                    help="Use deterministic mock LLM (no API calls).")
    sp.add_parser("score")
    sp.add_parser("weights")
    ar = sp.add_parser("autoresearch")
    ar.add_argument("--mock", action="store_true")
    sp.add_parser("metrics")
    sp.add_parser("reset")
    sp.add_parser("status")
    return p


HANDLERS = {
    "snapshot": cmd_snapshot,
    "cycle": cmd_cycle,
    "backtest": cmd_backtest,
    "score": cmd_score,
    "weights": cmd_weights,
    "autoresearch": cmd_autoresearch,
    "metrics": cmd_metrics,
    "reset": cmd_reset,
    "status": cmd_status,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    HANDLERS[args.cmd](args)


if __name__ == "__main__":
    main()
