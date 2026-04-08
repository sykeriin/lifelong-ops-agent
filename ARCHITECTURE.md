# Architecture Documentation

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Lifelong Ops Agent                        │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Baseline   │      │   Custom     │                    │
│  │   Agents     │      │   Agents     │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                     │                             │
│         └──────────┬──────────┘                             │
│                    │                                         │
│         ┌──────────▼──────────┐                            │
│         │  Evaluation Loop    │                            │
│         │  (lifelong_eval.py) │                            │
│         └──────────┬──────────┘                            │
│                    │                                         │
│    ┌───────────────┼───────────────┐                       │
│    │               │               │                        │
│    ▼               ▼               ▼                        │
│ ┌─────┐      ┌─────────┐     ┌────────┐                   │
│ │World│      │ Memory  │     │   KB   │                   │
│ │State│      │         │     │        │                   │
│ └─────┘      └─────────┘     └────────┘                   │
│    │               │               │                        │
│    └───────────────┼───────────────┘                       │
│                    │                                         │
│         ┌──────────▼──────────┐                            │
│         │   Task Generator    │                            │
│         │   & Grader          │                            │
│         └──────────┬──────────┘                            │
│                    │                                         │
│         ┌──────────▼──────────┐                            │
│         │   FastAPI Server    │                            │
│         │   (OpenEnv API)     │                            │
│         └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. World State (`env/world.py`)

**Purpose**: Manages the environment's temporal state across weeks.

**Key Design Decisions**:
- Pure functional design: `advance_week()` never mutates, always returns new state
- Deterministic transitions: No randomness in world evolution
- Explicit versioning: Policies have version strings (v1, v2, v3)

**Data Flow**:
```
get_initial_state() → WorldState(week=1)
    ↓
advance_week() → WorldState(week=2)
    ↓
advance_week() → WorldState(week=3)
```

**Why Pure Functions?**
- Reproducibility: Same sequence always produces same state
- Testability: Easy to verify transitions
- Debugging: Can inspect state at any point without side effects

### 2. Knowledge Base (`env/kb.py`)

**Purpose**: Versioned policy documentation with temporal validity.

**Key Features**:
- Articles have `valid_from_week` and `valid_until_week`
- Search filters by current week automatically
- Simple keyword-based scoring (no embeddings needed)

**Search Algorithm**:
```python
1. Filter articles by validity window
2. Compute keyword overlap score
3. Boost if query appears in title/body
4. Return top-k by score
```

**Why No Embeddings?**
- Deterministic: Same query always returns same results
- Fast: No model loading or inference
- Transparent: Easy to debug why an article matched

### 3. Task Generation (`env/tasks.py`)

**Purpose**: Generate tickets with ground truth baked in.

**Critical Design Choice**: Ground truth is computed at generation time, not grading time.

**Why?**
```python
# BAD: Compute ground truth at grading time
def grade(answer, ticket, current_world_state):
    # This uses CURRENT state, not state when ticket was created!
    correct_policy = current_world_state.current_policy
    # ❌ Wrong for legacy customers

# GOOD: Bake ground truth into ticket
def generate_ticket(world_state):
    ticket = {...}
    ticket["ground_truth"] = compute_truth(world_state)  # ✓ Correct
    return ticket
```

**Task Types**:

- **Task A**: Classification (category + priority)
  - Deterministic rules, no ambiguity
  - Tests basic comprehension

- **Task B**: Policy application
  - Must use correct policy version
  - Tests temporal reasoning

- **Task C**: Legacy handling
  - 50% legacy, 50% new customers
  - Tests memory and adaptation
  - Includes "traps" (wrong answers naive agents give)

### 4. Grading (`env/grader.py`)

**Purpose**: Deterministic scoring without LLM calls.

**Grading Strategy**:
- String matching for decisions ("approve"/"deny")
- Number extraction for policy windows (7, 14, 30)
- Penalty for mentioning wrong policy numbers

**Why String Matching?**
- Deterministic: Same answer always gets same score
- Fast: No API calls
- Transparent: Easy to see why score was given

**Scoring Breakdown**:
```
Task A: 0.5 (category) + 0.5 (priority)
Task B: 0.4 (decision) + 0.4 (reason) + 0.2 (no wrong numbers)
Task C: 0.4 (decision) + 0.3 (correct policy) + 0.3 (no trap)
```

### 5. Persistent Memory (`env/memory.py`)

**Purpose**: Simple key-value store that persists across episodes.

**Key Properties**:
- Never resets between episodes (only on explicit reset)
- No size limits (for simplicity)
- Values are strings (agents can JSON-serialize if needed)

**Design Philosophy**: Minimal viable memory system. Agents decide what to store and how to structure it.

### 6. Evaluation Loop (`eval/lifelong_eval.py`)

**Purpose**: Multi-phase evaluation with lifelong metrics.

**Protocol**:
```
Phase 1: Week 1 (60 episodes)
    ↓
advance_week()
    ↓
Phase 2: Week 2 (60 episodes) + track adaptation
    ↓
advance_week()
    ↓
Phase 3: Week 3 (60 episodes) + track adaptation
    ↓
Forgetting Probe: Week 1 tickets again (60 episodes)
    ↓
Compute metrics
```

**Adaptation Tracking**:
- Rolling window of 10 episodes
- Adaptation = first episode where rolling accuracy > 0.8
- If never reached, adaptation = total episodes

**Forgetting Calculation**:
```python
forgetting = acc_week_1 - acc_week_1_after_drift
# Positive = performance degraded
# Negative = performance improved (rare)
# Zero = no forgetting
```

### 7. FastAPI Server (`server.py`)

**Purpose**: OpenEnv-compliant HTTP API.

**State Management**:
- Global variables for current state (single-threaded)
- Memory persists across episodes
- Episode ends on Answer action or step limit

**Endpoints**:
- `POST /reset`: Initialize episode
- `POST /step`: Execute action
- `GET /state`: Debug current state
- `GET /health`: Health check

**Action Processing**:
```python
WriteMemory → Update memory, continue
ReadMemory → Return value, continue
SearchKB → Return articles, continue
Answer → Grade, set done=True, return reward
```

## Baseline Agents

### Stateless Agent

**Strategy**: Never uses memory, just searches KB and answers.

**Strengths**:
- Simple, fast
- No memory overhead

**Weaknesses**:
- Can't accumulate knowledge
- Slow adaptation (re-learns every episode)
- Forgets immediately

### Memory Agent

**Strategy**: Writes policy summaries to memory, reads before answering.

**Memory Keys**: `policy_summary_w{week}`

**Strengths**:
- Faster adaptation (learns once, reuses)
- Can handle legacy customers (remembers old policies)

**Weaknesses**:
- Still relies on KB search
- Memory can become stale
- No active memory management

## Design Principles

### 1. Determinism First

Every component is deterministic except:
- Ticket generation (controlled by seed)
- LLM calls (temperature=0.0 for reproducibility)

### 2. Ground Truth at Generation Time

Never recompute ground truth. Bake it into tickets.

### 3. Pure Functions for State

World state transitions are pure functions. No mutations.

### 4. Explicit Versioning

Policies have explicit versions. No implicit "current" policy.

### 5. Minimal Abstractions

Simple classes, no complex inheritance, no ORMs.

## Performance Characteristics

**Ticket Generation**: O(1) per ticket
**KB Search**: O(n) where n = number of articles (~12)
**Grading**: O(1) string matching
**Memory Operations**: O(1) dict lookup

**Bottleneck**: LLM API calls (2-3 per episode)

**Optimization Opportunities**:
- Batch LLM calls
- Cache KB search results
- Parallelize episode execution

## Testing Strategy

**Unit Tests**: Each component tested in isolation
**Integration Tests**: Full evaluation loop
**Validation Checks**: Determinism, reproducibility, correctness

**Key Invariants**:
1. Same seed → same tickets
2. Same answer → same score
3. advance_week() never mutates
4. Memory persists across episodes
5. Ground truth matches world state at generation time

## Extension Points

### Adding New Tasks

1. Add generator in `tasks.py`
2. Add grader in `grader.py`
3. Update `openenv.yaml`

### Adding New Metrics

1. Compute in `lifelong_eval.py`
2. Return in results dict
3. Print in `inference.py`

### Adding New Agents

1. Implement `act(observation, memory, world_state)` method
2. Return action dict with `type` field
3. Test with evaluation loop

### Scaling to More Weeks

1. Add cases to `advance_week()`
2. Add KB articles with new validity windows
3. Update evaluation protocol in `lifelong_eval.py`
