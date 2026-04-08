# STATUS: COMPLETE
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Union, Optional
import uuid

from env.world import WorldState, get_initial_state, advance_week
from env.memory import PersistentMemory
from env.tasks import generate_episode
from env.grader import grade
from env.kb import search_kb
import json

app = FastAPI()

# Global state
current_world_state: WorldState = get_initial_state()
current_memory: PersistentMemory = PersistentMemory()
current_episode_id: Optional[str] = None
current_ticket: Optional[dict] = None
current_step: int = 0
last_message: Optional[str] = None


# Pydantic models
class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    week: int
    episode_id: str
    step: int
    ticket: dict
    memory_keys: list[str]
    visible_plans: list[dict]
    message: Optional[str] = None


class WriteMemoryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["WriteMemory"]
    key: str
    value: str


class ReadMemoryAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["ReadMemory"]
    key: str


class SearchKBAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["SearchKB"]
    query: str


class AnswerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    type: Literal["Answer"]
    text: str


Action = Union[WriteMemoryAction, ReadMemoryAction, SearchKBAction, AnswerAction]


class Reward(BaseModel):
    """Typed reward model for OpenEnv compliance"""
    model_config = ConfigDict(extra="forbid")
    
    value: float
    breakdown: Optional[dict] = None


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    seed: int
    week: int = 1


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    action: Union[WriteMemoryAction, ReadMemoryAction, SearchKBAction, AnswerAction] = Field(..., discriminator="type")


class StepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    observation: Observation
    reward: Reward
    done: bool
    info: dict


@app.post("/reset")
def reset(request: ResetRequest) -> Observation:
    global current_world_state, current_memory, current_episode_id, current_ticket, current_step, last_message
    
    # Reset world to specified week
    current_world_state = get_initial_state()
    for _ in range(request.week - 1):
        current_world_state = advance_week(current_world_state)
    
    # Clear memory
    current_memory.reset()
    
    # Generate new episode
    current_episode_id = str(uuid.uuid4())
    task_type = "A"  # Default to task A for reset
    current_ticket = generate_episode(task_type, current_world_state, request.seed)
    current_step = 0
    last_message = None
    
    return _build_observation()


@app.post("/step")
def step(request: StepRequest) -> StepResponse:
    global current_step, last_message
    
    if current_episode_id is None or current_ticket is None:
        raise HTTPException(status_code=400, detail="No active episode. Call /reset first.")
    
    action = request.action
    reward_value = 0.0
    reward_breakdown = {}
    done = False
    info = {}
    
    # Process action
    if action.type == "WriteMemory":
        current_memory.write(action.key, action.value)
        last_message = f"Wrote to memory key: {action.key}"
        reward_value = 0.05  # Small reward for using memory
        reward_breakdown = {"memory_write": 0.05}
    
    elif action.type == "ReadMemory":
        value = current_memory.read(action.key)
        if value is not None:
            last_message = f"Memory[{action.key}]: {value}"
            reward_value = 0.05  # Reward for successful memory read
            reward_breakdown = {"memory_read_success": 0.05}
        else:
            last_message = f"Memory key '{action.key}' not found."
            reward_value = -0.02  # Small penalty for reading non-existent key
            reward_breakdown = {"memory_read_fail": -0.02}
    
    elif action.type == "SearchKB":
        results = search_kb(action.query, current_world_state, top_k=3)
        last_message = json.dumps(results, indent=2)
        reward_value = 0.1 if len(results) > 0 else 0.0  # Reward for successful search
        reward_breakdown = {"kb_search": reward_value, "results_found": len(results)}
    
    elif action.type == "Answer":
        # Grade the answer
        grade_result = grade(action.text, current_ticket, current_world_state)
        reward_value = grade_result["score"]
        reward_breakdown = {
            "final_score": grade_result["score"],
            "correct": grade_result["correct"]
        }
        done = True
        info = grade_result
        info["answer"] = action.text
        last_message = f"Answer submitted. Score: {reward_value:.2f}"
    
    current_step += 1
    
    # Check step limit
    if current_step >= 6 and not done:
        reward_value = 0.0
        reward_breakdown = {"step_limit_exceeded": True}
        done = True
        info = {"score": 0.0, "correct": False, "reason": "Step limit exceeded"}
        last_message = "Step limit exceeded."
    
    observation = _build_observation()
    
    return StepResponse(
        observation=observation,
        reward=Reward(value=reward_value, breakdown=reward_breakdown),
        done=done,
        info=info
    )


@app.get("/state")
def get_state():
    return {
        "week": current_world_state.week,
        "plans": {name: {
            "name": plan.name,
            "monthly_price": plan.monthly_price,
            "features": plan.features,
            "max_seats": plan.max_seats
        } for name, plan in current_world_state.plans.items()},
        "current_policy": {
            "version": current_world_state.current_policy.version,
            "refund_window_days": current_world_state.current_policy.refund_window_days,
            "upgrade_allowed": current_world_state.current_policy.upgrade_allowed,
            "downgrade_allowed": current_world_state.current_policy.downgrade_allowed,
            "priority_support": current_world_state.current_policy.priority_support
        },
        "feature_flags": current_world_state.feature_flags,
        "ticket_weights": current_world_state.ticket_weights,
        "memory_keys": current_memory.keys(),
        "current_episode_id": current_episode_id,
        "current_step": current_step
    }


@app.get("/health")
def health():
    return {"status": "ok"}


def _build_observation() -> Observation:
    """Build observation from current state."""
    visible_plans = [
        {"name": name, "monthly_price": plan.monthly_price}
        for name, plan in current_world_state.plans.items()
    ]
    
    return Observation(
        week=current_world_state.week,
        episode_id=current_episode_id,
        step=current_step,
        ticket=current_ticket,
        memory_keys=current_memory.keys(),
        visible_plans=visible_plans,
        message=last_message
    )
