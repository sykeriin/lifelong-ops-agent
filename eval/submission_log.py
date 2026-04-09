# STDOUT protocol for OpenEnv-style submission harness (see sampleinferencescript.md).
from __future__ import annotations

from typing import List, Optional

# Logged reward tokens use :.2f — avoid "0.00" / "1.00" if validators treat every reward as (0,1) open.
_LOG_R_MIN = 0.01
_LOG_R_MAX = 0.99


def _sanitize_action(s: str) -> str:
    return " ".join(s.split())


def _squeeze_logged_reward(r: float) -> float:
    x = float(r)
    if x <= 0.0:
        return _LOG_R_MIN
    if x >= 1.0:
        return _LOG_R_MAX
    if x < _LOG_R_MIN:
        return _LOG_R_MIN
    if x > _LOG_R_MAX:
        return _LOG_R_MAX
    return x


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_one_line = _sanitize_action(action)
    error_val = "null" if error is None else _sanitize_action(error)
    done_val = str(done).lower()
    r_log = _squeeze_logged_reward(reward)
    print(
        f"[STEP] step={step} action={action_one_line} reward={r_log:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    # score is already clamp_task_score(...) in [0.001, 0.999] — do not squeeze (would lift 0.001 → 0.01).
    rewards_str = ",".join(f"{_squeeze_logged_reward(r):.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )
