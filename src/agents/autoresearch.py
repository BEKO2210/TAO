"""Self-improvement engine.

Loop:
  1. Pick the lowest-Sharpe agent
  2. Use Claude to generate ONE targeted prompt modification
  3. Open a git feature branch and write the new prompt
  4. Wait 5 trading days (driven by the backtest_loop)
  5. Compare new Sharpe vs. old; merge or revert

State files:
    autoresearch_state.json  — current open experiments
    autoresearch_log.json    — historical log of all attempts
"""
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import registry, scorecard
from config.settings import (
    AUTORESEARCH_COOLDOWN_DAYS,
    AUTORESEARCH_LOOKBACK_DAYS,
    AUTORESEARCH_TEST_DAYS,
    STATE_DIR,
)
from utils import git_ops, llm
from utils.logging_utils import get_logger

logger = get_logger("autoresearch")

STATE_FILE = STATE_DIR / "autoresearch_state.json"
LOG_FILE = STATE_DIR / "autoresearch_log.json"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Experiment:
    agent: str
    prompt_file: str
    branch: str
    started_at: str
    target_review_date: str
    baseline_sharpe: float
    modification_summary: str
    status: str = "OPEN"          # OPEN | KEPT | REVERTED
    new_sharpe: Optional[float] = None
    completed_at: Optional[str] = None
    last_modified_at: Optional[str] = None  # used for cooldown

    def to_dict(self) -> Dict:
        return asdict(self)


def _load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"open_experiments": [], "cooldowns": {}}


def _save_state(state: Dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def _append_log(entry: Dict) -> None:
    log = []
    if LOG_FILE.exists():
        try:
            log = json.loads(LOG_FILE.read_text())
        except Exception:
            log = []
    log.append(entry)
    LOG_FILE.write_text(json.dumps(log, indent=2, default=str))


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------

def _on_cooldown(agent: str, today: date) -> bool:
    state = _load_state()
    last = state.get("cooldowns", {}).get(agent)
    if not last:
        return False
    last_d = date.fromisoformat(last)
    return (today - last_d).days < AUTORESEARCH_COOLDOWN_DAYS


def _set_cooldown(agent: str, today: date) -> None:
    state = _load_state()
    state.setdefault("cooldowns", {})[agent] = today.isoformat()
    _save_state(state)


# ---------------------------------------------------------------------------
# Prompt modification via Claude
# ---------------------------------------------------------------------------

MODIFY_SYSTEM = """You are improving an AI trading agent's prompt.

You will be given:
  1. The agent's current prompt
  2. Its recent recommendations and forward returns
  3. Its current rolling Sharpe ratio

Your job: propose ONE specific, targeted change to the prompt that addresses the
identified failure mode. The change should be:
  - Concrete and testable (a rule, threshold, filter, or constraint)
  - Small in scope (do not rewrite the whole prompt)
  - Justified by the data shown to you

Return JSON only:
{
  "diagnosis": "What's going wrong, in 1-2 sentences",
  "modification_summary": "One-sentence description of the change",
  "new_prompt": "The complete new prompt text, with the modification applied"
}
"""


def _agent_recent_recs(agent: str, n: int = 30) -> List[Dict]:
    recs = [r for r in scorecard.all_recommendations() if r.get("agent") == agent]
    recs.sort(key=lambda r: r.get("entry_date", ""))
    return recs[-n:]


def _generate_modification(agent: str) -> Optional[Dict[str, str]]:
    spec = registry.by_name(agent)
    if not spec:
        return None
    current_prompt = Path(spec.prompt_file).read_text() if Path(spec.prompt_file).exists() else ""
    recs = _agent_recent_recs(agent)
    sharpe = scorecard.agent_sharpe(agent)
    hit_rate = scorecard.agent_hit_rate(agent)
    user = (
        f"AGENT: {agent}\n"
        f"CURRENT SHARPE (rolling {AUTORESEARCH_LOOKBACK_DAYS}d): {sharpe:.3f}\n"
        f"HIT RATE: {hit_rate:.1%}\n\n"
        f"--- CURRENT PROMPT ---\n{current_prompt}\n\n"
        f"--- RECENT RECOMMENDATIONS (last {len(recs)}) ---\n"
        f"{json.dumps(recs, indent=2, default=str)}\n"
    )
    try:
        resp = llm.call_json(user=user, system=MODIFY_SYSTEM)
    except Exception as e:
        logger.error(f"Could not generate modification for {agent}: {e}")
        return None
    if not isinstance(resp, dict) or "new_prompt" not in resp:
        logger.warning(f"Bad modification response for {agent}: {resp}")
        return None
    return resp


# ---------------------------------------------------------------------------
# Experiment lifecycle
# ---------------------------------------------------------------------------

def _branch_name(agent: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"autoresearch/{agent}-{stamp}"


def start_experiment(agent: str, repo_root: Path) -> Optional[Experiment]:
    today = date.today()
    if _on_cooldown(agent, today):
        logger.info(f"{agent} is on cooldown; skipping.")
        return None
    spec = registry.by_name(agent)
    if not spec:
        return None

    baseline = scorecard.agent_sharpe(agent)
    mod = _generate_modification(agent)
    if not mod:
        return None

    branch = _branch_name(agent)
    starting_branch = git_ops.current_branch(cwd=repo_root)
    try:
        git_ops.create_branch(branch, cwd=repo_root)
        Path(spec.prompt_file).write_text(mod["new_prompt"])
        rel = Path(spec.prompt_file).relative_to(repo_root)
        git_ops.add([str(rel)], cwd=repo_root)
        git_ops.commit(
            f"autoresearch: {agent} — {mod['modification_summary']}",
            cwd=repo_root,
        )
    except Exception as e:
        logger.error(f"git ops failed for {agent}: {e}")
        try:
            git_ops.checkout(starting_branch, cwd=repo_root)
            git_ops.delete_branch(branch, cwd=repo_root)
        except Exception:
            pass
        return None
    finally:
        # Always come back to starting branch so the live system keeps running
        try:
            git_ops.checkout(starting_branch, cwd=repo_root)
        except Exception as e:
            logger.error(f"Could not checkout {starting_branch}: {e}")

    exp = Experiment(
        agent=agent,
        prompt_file=str(spec.prompt_file),
        branch=branch,
        started_at=today.isoformat(),
        target_review_date=(today + timedelta(days=AUTORESEARCH_TEST_DAYS)).isoformat(),
        baseline_sharpe=baseline,
        modification_summary=mod["modification_summary"],
    )
    state = _load_state()
    state["open_experiments"].append(exp.to_dict())
    _save_state(state)
    _set_cooldown(agent, today)
    _append_log({"event": "started", "experiment": exp.to_dict(), "diagnosis": mod.get("diagnosis", "")})
    logger.info(f"Started experiment {branch} for {agent}")
    return exp


def review_experiments(repo_root: Path) -> List[Dict]:
    """Check open experiments. If their review date has passed, keep or revert."""
    state = _load_state()
    today = date.today()
    completed = []
    still_open = []
    starting_branch = git_ops.current_branch(cwd=repo_root)

    for raw in state.get("open_experiments", []):
        exp = Experiment(**raw)
        if date.fromisoformat(exp.target_review_date) > today:
            still_open.append(exp.to_dict())
            continue

        new_sharpe = scorecard.agent_sharpe(exp.agent)
        improved = new_sharpe > exp.baseline_sharpe
        exp.new_sharpe = new_sharpe
        exp.completed_at = today.isoformat()
        exp.status = "KEPT" if improved else "REVERTED"

        try:
            if improved:
                # merge the branch back into current
                git_ops.merge(exp.branch, cwd=repo_root)
                git_ops.delete_branch(exp.branch, cwd=repo_root)
                logger.info(f"KEPT {exp.agent}: {exp.baseline_sharpe:.3f} → {new_sharpe:.3f}")
            else:
                # discard branch, no merge
                git_ops.delete_branch(exp.branch, cwd=repo_root)
                logger.info(f"REVERTED {exp.agent}: {exp.baseline_sharpe:.3f} → {new_sharpe:.3f}")
        except Exception as e:
            logger.error(f"git review failed for {exp.agent}: {e}")
        finally:
            try:
                git_ops.checkout(starting_branch, cwd=repo_root)
            except Exception:
                pass

        completed.append(exp.to_dict())
        _append_log({"event": "completed", "experiment": exp.to_dict()})

    state["open_experiments"] = still_open
    _save_state(state)
    return completed


def run_one_iteration(repo_root: Path) -> Dict[str, Any]:
    """Convenience wrapper: review then maybe start one new experiment."""
    completed = review_experiments(repo_root)

    state = _load_state()
    if state.get("open_experiments"):
        return {"started": None, "completed": completed,
                "reason": "An experiment is already open."}

    target = scorecard.lowest_sharpe_agent(registry.names())
    if target is None:
        return {"started": None, "completed": completed,
                "reason": "Not enough scored recommendations yet."}
    exp = start_experiment(target, repo_root)
    return {"started": exp.to_dict() if exp else None, "completed": completed}
