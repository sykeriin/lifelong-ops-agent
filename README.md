---
title: Lifelong Ops Agent Benchmark
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
tags:
  - openenv
  - reinforcement-learning
  - lifelong-learning
  - benchmark
  - agent-evaluation
pinned: false
---

# Lifelong Ops Agent Benchmark

## Problem Statement

Current agent benchmarks evaluate performance on static tasks with fixed rules. But real-world operations environments—especially SaaS customer support—are fundamentally non-stationary. Policies change, pricing evolves, features are added and deprecated, and legacy customers retain grandfathered terms while new customers face different rules. An agent that scores 95% on day one can catastrophically fail on day thirty if it hasn't adapted to policy drift or has forgotten how to handle legacy cases.

This benchmark addresses that gap. We simulate a realistic SaaS support environment where the world state (refund policies, plan pricing, feature availability) drifts across discrete "weeks." Agents are evaluated not just on per-ticket accuracy but on lifelong learning metrics: how quickly they adapt to new policies, and how much they forget about old ones. This is inspired by LifelongAgentBench, Continuum Memory Architectures (CMA), and LOCOMO research on catastrophic forgetting in LLM agents.

## Environment Overview

The environment simulates a SaaS company's support operations across three weeks. Each week introduces policy changes:

- **Week 1**: Initial state. Refund window is 7 days. Pro plan costs $29/mo with analytics.
- **Week 2**: Refund window changes to 30 days for NEW customers (legacy customers keep 7 days). Bulk export feature launches on Pro plan.
- **Week 3**: Refund window changes again to 14 days for new customers. Pro plan price increases to $39/mo for new customers (legacy keeps $29). Analytics deprecated from Pro plan.

Agents must handle three task types:

1. **Task A (Triage & Routing)**: Classify tickets by category (billing, feature, account, upgrade, refund) and assign priority (low, medium, high). Rules: refund requests and Enterprise customers are high priority.

2. **Task B (Policy Application)**: Apply the correct refund policy to customer requests. Must use the policy version that was active when the customer signed up, not the current policy.

3. **Task C (Legacy vs New Customer)**: The hardest task. 50% of tickets involve legacy customers who retain old pricing and policies. Agents must detect signup week and apply the correct grandfathered terms. Common failure mode: applying current 14-day window to a Week 2 customer who has 30 days.

## Lifelong Metrics

We measure three core metrics beyond per-episode accuracy:

1. **Accuracy per week**: `acc_t = (correct episodes in week t) / (total episodes in week t)`
   - Measures performance under current world state

2. **Forgetting score**: `forgetting = acc_1 - acc_1_after_drift`
   - After training on weeks 1-3, we re-test on week-1-style tickets
   - Positive forgetting score = agent degraded on old tasks after learning new policies
   - Catastrophic forgetting shows up as forgetting > 0.2

3. **Adaptation speed**: Number of episodes in a new week until rolling 10-episode accuracy exceeds 0.8
   - Measures how quickly agent learns new policies
   - Fast adaptation: < 15 episodes. Slow: > 40 episodes.

## Reward Structure

The environment provides both intermediate and terminal rewards:

- **Intermediate rewards** (encourage good behavior):
  - SearchKB with results: +0.1
  - WriteMemory: +0.05
  - ReadMemory (success): +0.05
  - ReadMemory (key not found): -0.02

- **Terminal reward** (final answer):
  - 0.0-1.0 based on deterministic grading
  - Task A: 0.5 (category) + 0.5 (priority)
  - Task B: 0.4 (decision) + 0.4 (reason) + 0.2 (no wrong policy)
  - Task C: 0.4 (decision) + 0.3 (correct policy) + 0.3 (no legacy trap)

- **Penalties**:
  - Step limit exceeded: 0.0
  - Reading non-existent memory: -0.02

## Action Space

Agents have four actions per episode (max 6 steps):

1. **SearchKB(query: str)**: Search knowledge base for policy articles. Returns top-3 matching articles with title, body, and validity window. Example: `SearchKB("refund policy")` returns v1, v2, v3 articles filtered by current week. **Reward: +0.1 for successful search**

2. **WriteMemory(key: str, value: str)**: Store information in persistent memory. Memory survives across episodes and weeks. Example: `WriteMemory("policy_summary_w2", "30-day refund window for new customers")`. **Reward: +0.05**

3. **ReadMemory(key: str)**: Retrieve stored information. Returns value or None. Example: `ReadMemory("policy_summary_w2")`. **Reward: +0.05 for success, -0.02 for missing key**

4. **Answer(text: str)**: Submit final answer. Episode ends. Graded on decision correctness, reasoning quality, and absence of wrong policy numbers. **Reward: 0.0-1.0 based on grading**

## Observation Space

The observation returned after each action contains:

- `week`: int - Current week (1-3)
- `episode_id`: str - Unique episode identifier (UUID)
- `step`: int - Current step in episode (0-5)
- `ticket`: dict - Current support ticket with:
  - `id`: str - Ticket ID
  - `task_type`: str - "A", "B", or "C"
  - `subject`: str - Ticket subject line
  - `body`: str - Ticket body text
  - `customer`: dict - Customer information (plan, signup_week, monthly_price_locked)
  - `ground_truth`: dict - Ground truth for grading (not visible to agent in real deployment)
- `memory_keys`: list[str] - List of available memory keys
- `visible_plans`: list[dict] - Current plan pricing (name and monthly_price only)
- `message`: str | None - Result message from last action (KB results, memory value, etc.)

## Baseline Results

| Agent      | W1 Acc | W2 Acc | W3 Acc | Forgetting | Adapt W2 | Adapt W3 |
|------------|--------|--------|--------|------------|----------|----------|
| Stateless  | TBD    | TBD    | TBD    | TBD        | TBD      | TBD      |
| Memory     | TBD    | TBD    | TBD    | TBD        | TBD      | TBD      |

(Run `python inference.py` with OPENAI_API_KEY set to populate this table)

## How to Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run evaluation (requires OPENAI_API_KEY)
export OPENAI_API_KEY=your_key_here
python inference.py

# Or run the server
uvicorn server:app --port 8080
```

## Docker Deployment

```bash
docker build -t lifelong-ops .
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8080:8080 lifelong-ops
```

## Research Grounding

This benchmark is grounded in three research directions:

1. **LifelongAgentBench** (2024): Introduced multi-phase evaluation for agents, measuring adaptation and forgetting across task distribution shifts.

2. **Continuum Memory Architectures (CMA)**: Proposes persistent memory mechanisms to mitigate catastrophic forgetting in sequential learning. Our PersistentMemory class is a minimal CMA implementation.

3. **LOCOMO (Lifelong Optimization of Continual Memory)**: Studies how agents should decide what to remember and what to forget. Task C (legacy customers) directly tests this: agents must remember old policies while learning new ones.

Key insight: SaaS ops is a perfect testbed for lifelong learning because policy versioning is explicit, ground truth is deterministic, and the forgetting/adaptation tradeoff is economically meaningful (wrong refund decisions cost money).

## OpenEnv Compliance

This environment implements the OpenEnv HTTP API:
- `POST /reset` - Initialize episode with seed and week
- `POST /step` - Execute action, get observation + reward
- `GET /state` - Inspect current world state (for debugging)
- `GET /health` - Health check

See `openenv.yaml` for full specification.
