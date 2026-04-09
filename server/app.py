# STATUS: COMPLETE
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Literal, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from env.grader import clamp_task_score, grade
from env.kb import search_kb
from env.memory import PersistentMemory
from env.tasks import generate_episode
from env.world import WorldState, advance_week, get_initial_state

app = FastAPI(
    title="Lifelong Ops Agent Benchmark",
    version="0.1.0",
    description="OpenEnv-compatible HTTP API (simulation mode).",
)

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
    # Defaults allow POST {} from HF / OpenEnv preflight (validate-submission.sh).
    seed: int = 42
    week: int = 1


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Union[WriteMemoryAction, ReadMemoryAction, SearchKBAction, AnswerAction] = Field(
        ..., discriminator="type"
    )


class StepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: Observation
    reward: Reward
    done: bool
    info: dict


@app.post("/reset")
async def reset(http_request: Request) -> Observation:
    """Accept no body, empty body, or JSON (OpenEnv / HF may POST with no body)."""
    global current_world_state, current_memory, current_episode_id, current_ticket, current_step, last_message

    raw = await http_request.body()
    if not raw or not raw.strip():
        request = ResetRequest()
    else:
        try:
            request = ResetRequest.model_validate_json(raw)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

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
            "correct": grade_result["correct"],
        }
        done = True
        info = grade_result
        info["answer"] = action.text
        last_message = f"Answer submitted. Score: {reward_value:.2f}"

    current_step += 1

    # Check step limit
    if current_step >= 6 and not done:
        reward_value = clamp_task_score(0.0)
        reward_breakdown = {"step_limit_exceeded": True}
        done = True
        info = {
            "score": reward_value,
            "correct": False,
            "reason": "Step limit exceeded",
        }
        last_message = "Step limit exceeded."

    observation = _build_observation()

    return StepResponse(
        observation=observation,
        reward=Reward(value=reward_value, breakdown=reward_breakdown),
        done=done,
        info=info,
    )


@app.get("/state")
def get_state():
    return {
        "week": current_world_state.week,
        "plans": {
            name: {
                "name": plan.name,
                "monthly_price": plan.monthly_price,
                "features": plan.features,
                "max_seats": plan.max_seats,
            }
            for name, plan in current_world_state.plans.items()
        },
        "current_policy": {
            "version": current_world_state.current_policy.version,
            "refund_window_days": current_world_state.current_policy.refund_window_days,
            "upgrade_allowed": current_world_state.current_policy.upgrade_allowed,
            "downgrade_allowed": current_world_state.current_policy.downgrade_allowed,
            "priority_support": current_world_state.current_policy.priority_support,
        },
        "feature_flags": current_world_state.feature_flags,
        "ticket_weights": current_world_state.ticket_weights,
        "memory_keys": current_memory.keys(),
        "current_episode_id": current_episode_id,
        "current_step": current_step,
    }


@app.get("/api")
def api_discovery():
    """JSON index for tools and scripts (browser root redirects to /ui/)."""
    return {
        "service": "lifelong-ops-agent",
        "docs": "OpenEnv HTTP API",
        "playground": "/ui/",
        "health": "/health",
        "reset": "POST /reset",
        "step": "POST /step",
        "state": "GET /state",
    }


@app.get("/")
def root():
    """HF Space visitors: show playground HTML; use GET /api for JSON discovery."""
    return RedirectResponse(url="/ui/", status_code=307)


@app.get("/playground")
def playground_redirect():
    """Shortcut to the browser UI (same as /ui/)."""
    return RedirectResponse(url="/ui/")


@app.get("/health")
def health():
    # openenv-core runtime validate expects status == "healthy"
    return {"status": "healthy"}


@app.get("/metadata")
def metadata():
    return {
        "name": "lifelong-ops-agent",
        "description": (
            "SaaS support/ops environment where policies and pricing drift across weeks; "
            "evaluates adaptation and forgetting (OpenEnv HTTP API)."
        ),
    }


@app.get("/schema")
def schema():
    """Minimal schema shells for openenv validate (full contract in openenv.yaml)."""
    return {
        "action": {"type": "discriminated_union", "discriminator": "type"},
        "observation": {"type": "object"},
        "state": {"type": "object"},
    }


@app.post("/mcp")
def mcp_stub() -> dict:
    """Stub MCP JSON-RPC envelope for openenv runtime validate."""
    return {"jsonrpc": "2.0", "id": None, "result": None}


_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount(
        "/ui",
        StaticFiles(directory=str(_STATIC_DIR), html=True),
        name="ui",
    )


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
        message=last_message,
    )


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
