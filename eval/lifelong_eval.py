# STATUS: COMPLETE
from __future__ import annotations

import json
import sys
from typing import Any

from env.grader import clamp_task_score, grade
from env.kb import search_kb
from env.memory import PersistentMemory
from env.tasks import generate_batch
from env.world import WorldState, advance_week, get_initial_state

_TASK_LOG_NAMES = {"A": "task_a", "B": "task_b", "C": "task_c"}
_MAX_AGENT_STEPS = 6


def _action_to_str(action: dict) -> str:
    t = action["type"]
    if t == "SearchKB":
        return f"SearchKB({action['query']!r})"
    if t == "WriteMemory":
        return f"WriteMemory({action['key']!r})"
    if t == "ReadMemory":
        return f"ReadMemory({action['key']!r})"
    if t == "Answer":
        body = (action.get("text") or "")[:200].replace("\n", " ").replace("\r", "")
        return f"Answer({body!r})"
    return repr(action)


def run_lifelong_eval(
    agent,
    n_per_task: int = 20,
    seed: int = 42,
    *,
    emit_submission_logs: bool = False,
    log_benchmark: str = "lifelong-ops-agent",
    log_model: str = "",
    success_score_threshold: float = 0.1,
) -> dict:
    """
    Runs the full lifelong evaluation protocol.
    
    Protocol:
    1. Initialize world at week=1, create fresh PersistentMemory
    2. Phase 1: generate n_per_task tickets for each task type (A, B, C) at week 1
       - Run agent on all tickets, keeping memory across episodes
       - Record per-ticket scores → compute acc_1
    3. advance_week() → week 2
    4. Phase 2: generate n_per_task tickets for each task type at week 2
       - Continue with SAME memory object
       - Record scores → compute acc_2
       - Record "adaptation": how many week-2 episodes until rolling accuracy > 0.8
    5. advance_week() → week 3
    6. Phase 3: generate n_per_task tickets for each task type at week 3
       - Continue with SAME memory
       - Record scores → compute acc_3
    7. Forgetting probe: generate n_per_task week-1-style tickets, run agent (same memory)
       - Record scores → compute acc_1_after
       - forgetting = acc_1 - acc_1_after
    
    Returns:
    {
      "acc_week_1": float,
      "acc_week_2": float,
      "acc_week_3": float,
      "acc_1_after_drift": float,
      "forgetting_score": float,
      "adaptation_episodes_w2": int,
      "adaptation_episodes_w3": int,
      "per_task_breakdown": dict,
      "memory_snapshot_end": dict
    }
    """
    world_state = get_initial_state()
    memory = PersistentMemory()

    def _log(msg: str) -> None:
        dest = sys.stderr if emit_submission_logs else sys.stdout
        print(msg, file=dest, flush=True)

    all_scores = {
        "week_1": [],
        "week_2": [],
        "week_3": [],
        "week_1_after": []
    }

    per_task_breakdown = {}

    # Phase 1: Week 1
    _log("Phase 1: Week 1")
    week_1_scores = _run_phase(
        agent,
        world_state,
        memory,
        n_per_task,
        seed,
        "week_1",
        per_task_breakdown,
        emit_submission_logs=emit_submission_logs,
        log_benchmark=log_benchmark,
        log_model=log_model,
        success_score_threshold=success_score_threshold,
    )
    all_scores["week_1"] = week_1_scores
    acc_1 = (
        sum(week_1_scores) / len(week_1_scores) if week_1_scores else clamp_task_score(0.0)
    )
    
    # Advance to week 2
    world_state = advance_week(world_state)
    
    # Phase 2: Week 2
    _log("Phase 2: Week 2")
    week_2_scores, adapt_w2 = _run_phase_with_adaptation(
        agent,
        world_state,
        memory,
        n_per_task,
        seed + 1000,
        "week_2",
        per_task_breakdown,
        emit_submission_logs=emit_submission_logs,
        log_benchmark=log_benchmark,
        log_model=log_model,
        success_score_threshold=success_score_threshold,
    )
    all_scores["week_2"] = week_2_scores
    acc_2 = sum(week_2_scores) / len(week_2_scores) if week_2_scores else 0.0
    
    # Advance to week 3
    world_state = advance_week(world_state)
    
    # Phase 3: Week 3
    _log("Phase 3: Week 3")
    week_3_scores, adapt_w3 = _run_phase_with_adaptation(
        agent,
        world_state,
        memory,
        n_per_task,
        seed + 2000,
        "week_3",
        per_task_breakdown,
        emit_submission_logs=emit_submission_logs,
        log_benchmark=log_benchmark,
        log_model=log_model,
        success_score_threshold=success_score_threshold,
    )
    all_scores["week_3"] = week_3_scores
    acc_3 = (
        sum(week_3_scores) / len(week_3_scores) if week_3_scores else clamp_task_score(0.0)
    )
    
    # Forgetting probe: Week 1 tickets again
    _log("Forgetting probe: Week 1 tickets")
    week_1_state = get_initial_state()
    week_1_after_scores = _run_phase(
        agent,
        week_1_state,
        memory,
        n_per_task,
        seed + 3000,
        "week_1_after",
        per_task_breakdown,
        emit_submission_logs=emit_submission_logs,
        log_benchmark=log_benchmark,
        log_model=log_model,
        success_score_threshold=success_score_threshold,
    )
    all_scores["week_1_after"] = week_1_after_scores
    acc_1_after = (
        sum(week_1_after_scores) / len(week_1_after_scores)
        if week_1_after_scores
        else clamp_task_score(0.0)
    )
    
    forgetting_score = acc_1 - acc_1_after
    
    return {
        "acc_week_1": acc_1,
        "acc_week_2": acc_2,
        "acc_week_3": acc_3,
        "acc_1_after_drift": acc_1_after,
        "forgetting_score": forgetting_score,
        "adaptation_episodes_w2": adapt_w2,
        "adaptation_episodes_w3": adapt_w3,
        "per_task_breakdown": per_task_breakdown,
        "memory_snapshot_end": memory.snapshot()
    }


def _run_phase(
    agent,
    world_state: WorldState,
    memory: PersistentMemory,
    n_per_task: int,
    seed: int,
    phase_name: str,
    per_task_breakdown: dict,
    *,
    emit_submission_logs: bool = False,
    log_benchmark: str = "",
    log_model: str = "",
    success_score_threshold: float = 0.1,
) -> list[float]:
    """Run a single phase and return scores."""
    scores = []

    if phase_name not in per_task_breakdown:
        per_task_breakdown[phase_name] = {}

    for task_type in ["A", "B", "C"]:
        tickets = generate_batch(task_type, world_state, n_per_task, seed)
        task_scores = []

        for ticket in tickets:
            score = _run_episode(
                agent,
                ticket,
                world_state,
                memory,
                emit_submission_logs=emit_submission_logs,
                log_benchmark=log_benchmark,
                log_model=log_model,
                success_score_threshold=success_score_threshold,
            )
            scores.append(score)
            task_scores.append(score)
        
        per_task_breakdown[phase_name][task_type] = (
            sum(task_scores) / len(task_scores) if task_scores else clamp_task_score(0.0)
        )
        seed += 100
    
    return scores


def _run_phase_with_adaptation(
    agent,
    world_state: WorldState,
    memory: PersistentMemory,
    n_per_task: int,
    seed: int,
    phase_name: str,
    per_task_breakdown: dict,
    *,
    emit_submission_logs: bool = False,
    log_benchmark: str = "",
    log_model: str = "",
    success_score_threshold: float = 0.1,
) -> tuple[list[float], int]:
    """Run a phase and track adaptation episodes."""
    scores = []
    adaptation_episodes = -1
    rolling_window = 10

    if phase_name not in per_task_breakdown:
        per_task_breakdown[phase_name] = {}

    for task_type in ["A", "B", "C"]:
        tickets = generate_batch(task_type, world_state, n_per_task, seed)
        task_scores = []

        for i, ticket in enumerate(tickets):
            score = _run_episode(
                agent,
                ticket,
                world_state,
                memory,
                emit_submission_logs=emit_submission_logs,
                log_benchmark=log_benchmark,
                log_model=log_model,
                success_score_threshold=success_score_threshold,
            )
            scores.append(score)
            task_scores.append(score)
            
            # Check for adaptation
            if adaptation_episodes == -1 and len(scores) >= rolling_window:
                recent_scores = scores[-rolling_window:]
                rolling_acc = sum(recent_scores) / len(recent_scores)
                if rolling_acc > 0.8:
                    adaptation_episodes = len(scores)
        
        per_task_breakdown[phase_name][task_type] = (
            sum(task_scores) / len(task_scores) if task_scores else clamp_task_score(0.0)
        )
        seed += 100
    
    if adaptation_episodes == -1:
        adaptation_episodes = len(scores)  # Never reached 0.8
    
    return scores, adaptation_episodes


def _run_episode(
    agent,
    ticket: dict,
    world_state: WorldState,
    memory: PersistentMemory,
    *,
    emit_submission_logs: bool = False,
    log_benchmark: str = "lifelong-ops-agent",
    log_model: str = "",
    success_score_threshold: float = 0.1,
) -> float:
    """Run a single episode with the agent."""
    rewards: list[float] = []
    steps_logged = 0
    log_ended = False
    log_step = log_end = log_start = None  # type: ignore[assignment]
    if emit_submission_logs:
        from eval.submission_log import log_end as _log_end
        from eval.submission_log import log_start as _log_start
        from eval.submission_log import log_step as _log_step

        log_end, log_start, log_step = _log_end, _log_start, _log_step
        log_task = _TASK_LOG_NAMES.get(ticket["task_type"], ticket["task_type"])
        log_start(task=log_task, env=log_benchmark, model=log_model)

    def _emit_end(success: bool, steps: int, score: float, rlist: list[float]) -> None:
        nonlocal log_ended
        if emit_submission_logs and log_end is not None and not log_ended:
            log_end(success, steps, score, rlist)
            log_ended = True

    try:
        observation: dict[str, Any] = {
            "week": world_state.week,
            "episode_id": ticket["id"],
            "step": 0,
            "ticket": ticket,
            "memory_keys": memory.keys(),
            "visible_plans": [
                {"name": name, "monthly_price": plan.monthly_price}
                for name, plan in world_state.plans.items()
            ],
            "message": None,
        }

        for step_idx in range(_MAX_AGENT_STEPS):
            observation["step"] = step_idx

            try:
                action = agent.act(observation, memory, world_state)
            except Exception as exc:
                if emit_submission_logs and log_step is not None:
                    steps_logged += 1
                    err = str(exc).replace("\n", " ")
                    log_step(steps_logged, "(agent_error)", 0.0, True, err)
                    rewards.append(0.0)
                _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
                return clamp_task_score(0.0)

            astr = _action_to_str(action)

            if action["type"] == "WriteMemory":
                memory.write(action["key"], action["value"])
                observation["message"] = f"Wrote to memory key: {action['key']}"
                r = 0.05
                steps_logged += 1
                rewards.append(r)
                forced_done = steps_logged >= _MAX_AGENT_STEPS
                if emit_submission_logs and log_step is not None:
                    log_step(steps_logged, astr, r, forced_done, None)
                    if forced_done:
                        _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
                        return clamp_task_score(0.0)
                observation["memory_keys"] = memory.keys()
                continue

            if action["type"] == "ReadMemory":
                value = memory.read(action["key"])
                if value is not None:
                    observation["message"] = f"Memory[{action['key']}]: {value}"
                    r = 0.05
                else:
                    observation["message"] = f"Memory key '{action['key']}' not found."
                    r = -0.02
                steps_logged += 1
                rewards.append(r)
                forced_done = steps_logged >= _MAX_AGENT_STEPS
                if emit_submission_logs and log_step is not None:
                    log_step(steps_logged, astr, r, forced_done, None)
                    if forced_done:
                        _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
                        return clamp_task_score(0.0)
                observation["memory_keys"] = memory.keys()
                continue

            if action["type"] == "SearchKB":
                results = search_kb(action["query"], world_state, top_k=3)
                observation["message"] = json.dumps(results, indent=2)
                r = 0.1 if len(results) > 0 else 0.0
                steps_logged += 1
                rewards.append(r)
                forced_done = steps_logged >= _MAX_AGENT_STEPS
                if emit_submission_logs and log_step is not None:
                    log_step(steps_logged, astr, r, forced_done, None)
                    if forced_done:
                        _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
                        return clamp_task_score(0.0)
                observation["memory_keys"] = memory.keys()
                continue

            if action["type"] == "Answer":
                answer_text = action["text"]
                grade_result = grade(answer_text, ticket, world_state)
                score = grade_result["score"]
                steps_logged += 1
                rewards.append(score)
                if emit_submission_logs and log_step is not None:
                    log_step(steps_logged, astr, score, True, None)
                _emit_end(score >= success_score_threshold, steps_logged, score, rewards)
                return score

            if emit_submission_logs and log_step is not None:
                steps_logged += 1
                log_step(steps_logged, astr, 0.0, True, "invalid_action_type")
                rewards.append(0.0)
            _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
            return clamp_task_score(0.0)

        _emit_end(False, steps_logged, clamp_task_score(0.0), rewards)
        return clamp_task_score(0.0)
    finally:
        if emit_submission_logs and log_end is not None and not log_ended:
            log_end(False, steps_logged, clamp_task_score(0.0), rewards if rewards else [])
