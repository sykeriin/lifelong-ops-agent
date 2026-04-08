# STATUS: COMPLETE
from env.world import get_initial_state, advance_week, WorldState
from env.memory import PersistentMemory
from env.tasks import generate_batch
from env.grader import grade
from typing import Any


def run_lifelong_eval(agent, n_per_task: int = 20, seed: int = 42) -> dict:
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
    
    all_scores = {
        "week_1": [],
        "week_2": [],
        "week_3": [],
        "week_1_after": []
    }
    
    per_task_breakdown = {}
    
    # Phase 1: Week 1
    print("Phase 1: Week 1")
    week_1_scores = _run_phase(agent, world_state, memory, n_per_task, seed, "week_1", per_task_breakdown)
    all_scores["week_1"] = week_1_scores
    acc_1 = sum(week_1_scores) / len(week_1_scores) if week_1_scores else 0.0
    
    # Advance to week 2
    world_state = advance_week(world_state)
    
    # Phase 2: Week 2
    print("Phase 2: Week 2")
    week_2_scores, adapt_w2 = _run_phase_with_adaptation(agent, world_state, memory, n_per_task, seed + 1000, "week_2", per_task_breakdown)
    all_scores["week_2"] = week_2_scores
    acc_2 = sum(week_2_scores) / len(week_2_scores) if week_2_scores else 0.0
    
    # Advance to week 3
    world_state = advance_week(world_state)
    
    # Phase 3: Week 3
    print("Phase 3: Week 3")
    week_3_scores, adapt_w3 = _run_phase_with_adaptation(agent, world_state, memory, n_per_task, seed + 2000, "week_3", per_task_breakdown)
    all_scores["week_3"] = week_3_scores
    acc_3 = sum(week_3_scores) / len(week_3_scores) if week_3_scores else 0.0
    
    # Forgetting probe: Week 1 tickets again
    print("Forgetting probe: Week 1 tickets")
    week_1_state = get_initial_state()
    week_1_after_scores = _run_phase(agent, week_1_state, memory, n_per_task, seed + 3000, "week_1_after", per_task_breakdown)
    all_scores["week_1_after"] = week_1_after_scores
    acc_1_after = sum(week_1_after_scores) / len(week_1_after_scores) if week_1_after_scores else 0.0
    
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


def _run_phase(agent, world_state: WorldState, memory: PersistentMemory, n_per_task: int, seed: int, phase_name: str, per_task_breakdown: dict) -> list[float]:
    """Run a single phase and return scores."""
    scores = []
    
    if phase_name not in per_task_breakdown:
        per_task_breakdown[phase_name] = {}
    
    for task_type in ["A", "B", "C"]:
        tickets = generate_batch(task_type, world_state, n_per_task, seed)
        task_scores = []
        
        for ticket in tickets:
            score = _run_episode(agent, ticket, world_state, memory)
            scores.append(score)
            task_scores.append(score)
        
        per_task_breakdown[phase_name][task_type] = sum(task_scores) / len(task_scores) if task_scores else 0.0
        seed += 100
    
    return scores


def _run_phase_with_adaptation(agent, world_state: WorldState, memory: PersistentMemory, n_per_task: int, seed: int, phase_name: str, per_task_breakdown: dict) -> tuple[list[float], int]:
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
            score = _run_episode(agent, ticket, world_state, memory)
            scores.append(score)
            task_scores.append(score)
            
            # Check for adaptation
            if adaptation_episodes == -1 and len(scores) >= rolling_window:
                recent_scores = scores[-rolling_window:]
                rolling_acc = sum(recent_scores) / len(recent_scores)
                if rolling_acc > 0.8:
                    adaptation_episodes = len(scores)
        
        per_task_breakdown[phase_name][task_type] = sum(task_scores) / len(task_scores) if task_scores else 0.0
        seed += 100
    
    if adaptation_episodes == -1:
        adaptation_episodes = len(scores)  # Never reached 0.8
    
    return scores, adaptation_episodes


def _run_episode(agent, ticket: dict, world_state: WorldState, memory: PersistentMemory) -> float:
    """Run a single episode with the agent."""
    # Create observation
    observation = {
        "week": world_state.week,
        "episode_id": ticket["id"],
        "step": 0,
        "ticket": ticket,
        "memory_keys": memory.keys(),
        "visible_plans": [
            {"name": name, "monthly_price": plan.monthly_price}
            for name, plan in world_state.plans.items()
        ],
        "message": None
    }
    
    answer_text = None
    max_steps = 6
    
    for step in range(max_steps):
        observation["step"] = step
        
        # Get action from agent
        action = agent.act(observation, memory, world_state)
        
        # Process action
        if action["type"] == "WriteMemory":
            memory.write(action["key"], action["value"])
            observation["message"] = f"Wrote to memory key: {action['key']}"
        
        elif action["type"] == "ReadMemory":
            value = memory.read(action["key"])
            if value is not None:
                observation["message"] = f"Memory[{action['key']}]: {value}"
            else:
                observation["message"] = f"Memory key '{action['key']}' not found."
        
        elif action["type"] == "SearchKB":
            from env.kb import search_kb
            import json
            results = search_kb(action["query"], world_state, top_k=3)
            observation["message"] = json.dumps(results, indent=2)
        
        elif action["type"] == "Answer":
            answer_text = action["text"]
            break
        
        observation["memory_keys"] = memory.keys()
    
    # Grade the answer
    if answer_text is None:
        return 0.0
    
    grade_result = grade(answer_text, ticket, world_state)
    return grade_result["score"]
