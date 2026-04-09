---
title: Lifelong Ops Agent Benchmark
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
tags:
  - openenv
  - reinforcement-learning
  - lifelong-learning
  - benchmark
  - agent-evaluation
pinned: false
---

# Lifelong Ops Agent Benchmark

**An OpenEnv-compatible benchmark for evaluating LLM agents under scheduled policy drift.** Real SaaS support environments are non-stationary: refund windows change, pricing shifts, features launch and deprecate, and legacy customers keep grandfathered terms. This benchmark measures whether agents can **adapt** to new rules without **forgetting** old ones — the first OpenEnv environment to explicitly score **catastrophic forgetting** alongside per-ticket accuracy.

> Live API: [HF Space](https://huggingface.co/spaces/sykeriin/lifelong-ops-agent) | Interactive playground: `/ui/` | Spec: `openenv.yaml`

---

## Why this benchmark exists

Current agent evaluations assume a fixed world. But a support agent deployed for weeks faces **distribution shift**: the refund policy it memorized on day one may be wrong by day fifteen. LifelongAgentBench, Continuum Memory Architectures, and LOCOMO research all identify this gap — realistic, non-stationary environments with **explicit forgetting metrics** are missing from the OpenEnv ecosystem. This benchmark fills that gap with a lightweight SaaS simulation that runs in minutes, not hours.

---

## Environment overview

A SaaS company's support operations across **three weeks**, each introducing policy changes:

| Week | Refund window | Pro plan price | Key change |
|------|---------------|----------------|------------|
| 1 | 7 days | $29/mo | Baseline state |
| 2 | 30 days (new customers) | $29/mo | Bulk export launches; legacy customers keep 7-day window |
| 3 | 14 days (new customers) | $39/mo (new customers) | Analytics deprecated from Pro; legacy keeps $29 and 30-day window |

Legacy customers **always retain the policy that was active when they signed up**. This is the core difficulty: an agent must track **which** version of the rules applies to **which** customer.

---

## Tasks (3 tasks, easy to hard)

### Task A — Ticket triage and routing (easy)

| | |
|---|---|
| **Log id** | `task_a` |
| **Goal** | Classify the ticket by category (billing, feature, account, upgrade, refund) and assign priority (low, medium, high) |
| **Why easy** | Rules are static: refund requests and Enterprise customers are always high priority |
| **Grader** | +0.5 for correct category (case-insensitive substring), +0.5 for correct priority. Deterministic, partial credit. |

### Task B — Policy application (medium)

| | |
|---|---|
| **Log id** | `task_b` |
| **Goal** | Apply the correct refund/upgrade policy to a customer request; produce the right decision (approve/deny) with the right reasoning |
| **Why medium** | The agent must use the **current** policy version — but the version changes each week |
| **Grader** | +0.4 decision correct, +0.4 key reason cited (correct refund window number), +0.2 no wrong policy numbers mentioned. Deterministic. |

### Task C — Legacy vs new customers (hard)

| | |
|---|---|
| **Log id** | `task_c` |
| **Goal** | Apply the **versioned** policy that matches the customer's signup week, not the current week |
| **Why hard** | 50% of tickets involve legacy customers with grandfathered terms. The common LLM failure mode is applying the **current** 14-day window to a Week-2 customer who actually has **30 days**. Ground truth encodes a `legacy_trap` flag that catches exactly this confusion. |
| **Grader** | +0.4 decision correct, +0.3 correct policy version implied (right window/price numbers), +0.3 legacy trap NOT triggered (wrong-version numbers absent). Deterministic. |

### Grader contract

All graders share the same interface: `grade(answer_text, ticket, world_state) -> {"score": float, "correct": bool, ...}`. Scores are **deterministic** (no LLM-in-the-loop grading), always in the **open interval (0, 1)** per platform requirements, and support **partial credit** so agents that get the decision right but cite the wrong policy still score above floor.

---

## Lifelong evaluation protocol

```
Phase 1 (Week 1)  ──►  advance_week()  ──►  Phase 2 (Week 2)  ──►  advance_week()  ──►  Phase 3 (Week 3)
                                                                                               │
                                                                                    Forgetting probe
                                                                                    (Week 1 tickets again,
                                                                                     same memory object)
```

**Persistent memory** is shared across all phases — the same `PersistentMemory` object persists from Week 1 through the forgetting probe. This is what makes the benchmark **lifelong**: an agent that blindly overwrites its memory with Week 3 policy summaries will fail on Week 1 tickets in the probe.

### Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Accuracy (per week)** | `acc_t = mean(scores in week t)` | Raw performance under current world state |
| **Forgetting** | `acc_1 - acc_1_after_drift` | Positive = degraded on old tasks after learning new policies; > 0.2 is catastrophic |
| **Adaptation speed** | Episodes until rolling-10 accuracy > 0.8 | Fast: < 15. Slow: > 40. |

---

## Reward structure

The environment provides **trajectory signal**, not just a terminal grade:

| Action | Reward | Purpose |
|--------|--------|---------|
| `SearchKB` (results found) | +0.10 | Encourage information gathering |
| `WriteMemory` | +0.05 | Encourage persistent storage |
| `ReadMemory` (key exists) | +0.05 | Encourage memory use |
| `ReadMemory` (key missing) | -0.02 | Penalize speculative reads |
| `Answer` (terminal) | 0.001–0.999 | Graded score (partial credit) |
| Step limit exceeded (6 steps) | Floor score | Hard cap prevents infinite loops |
| Invalid action type | Floor score | Terminal, prevents undefined behavior |

---

## Action and observation spaces

**Actions** (discriminated union, max 6 steps per episode):

- `SearchKB(query)` — returns top-3 KB articles filtered by current week validity
- `WriteMemory(key, value)` — persists across episodes and weeks
- `ReadMemory(key)` — returns value or None
- `Answer(text)` — ends episode, triggers grading

**Observation** (returned after every action):

- `week` (int), `episode_id` (str), `step` (int 0–5)
- `ticket` — id, task_type, subject, body, customer info (plan, signup_week, locked price)
- `memory_keys` — list of stored keys
- `visible_plans` — current plan names and prices (partial view; full policy requires KB search)
- `message` — result from last action (KB articles, memory value, etc.)

---

## Baseline results

Model: **llama3.1:8b** via local Ollama. `N_PER_TASK=5` (smoke protocol, 60 episodes total). Seed 42.

| Metric | Run 1 | Run 2 |
|--------|-------|-------|
| **W1 accuracy** | 0.653 | 0.657 |
| **W2 accuracy** | 0.860 | 0.723 |
| **W3 accuracy** | 0.813 | 0.760 |
| **Forgetting** | 0.020 | -0.008 |
| **Adapt W2** | 10 episodes | 39 episodes |
| **Adapt W3** | 12 episodes | 28 episodes |

Per-task (Run 1): Task A 0.60→0.90→0.70 | Task B 0.76→0.92→0.88 | Task C 0.60→0.76→0.86

**Key observations:** (1) Task C improves across weeks as memory accumulates policy summaries — but forgetting is low, suggesting the agent doesn't overwrite old knowledge. (2) With a fast hosted API (Groq, HF router) and `N_PER_TASK=20`, full protocol completes well under the 20-minute budget on 2 vCPU / 8 GB.

---

## Quick start

```bash
pip install -r requirements.txt

# Full protocol (hosted API, ~10 min)
export API_BASE_URL=https://api.groq.com/openai/v1
export MODEL_NAME=llama-3.1-70b-versatile
export GROQ_API_KEY=your_key
export N_PER_TASK=20
python inference.py

# Smoke test (local Ollama, ~20 min)
export API_BASE_URL=http://127.0.0.1:11434
export MODEL_NAME=llama3.1:8b
export N_PER_TASK=5
python inference.py
```

Structured logs (`[START]`/`[STEP]`/`[END]`) go to **stdout** (always on by default). Human-readable progress goes to **stderr**.

## Docker

```bash
docker build -t lifelong-ops .
docker run -p 7860:7860 lifelong-ops
curl http://127.0.0.1:7860/health
# Browser playground: http://127.0.0.1:7860/ui/
```

---

## OpenEnv compliance

Opening the Space base URL in a browser redirects to **`/ui/`** (playground). Machine-readable service index: **`GET /api`**.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Redirect to `/ui/` |
| `/api` | GET | JSON service index (routes and links) |
| `/reset` | POST | New episode (body optional: `{}` or omit) |
| `/step` | POST | Execute action, get observation + reward |
| `/state` | GET | Current world state (debugging) |
| `/health` | GET | `{"status": "healthy"}` |
| `/metadata` | GET | Benchmark name + description |
| `/schema` | GET | Action/observation/state schemas |
| `/mcp` | POST | JSON-RPC stub |
| `/ui/` | GET | Interactive browser playground |

`openenv validate` passes both locally and against the live HF Space URL. See `openenv.yaml` for the full typed specification.

---

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `API_BASE_URL` | Yes (hosted) | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint |
| `MODEL_NAME` | Yes | `llama-3.1-70b-versatile` | Provider's model id |
| `OPENAI_API_KEY` / `HF_TOKEN` / `GROQ_API_KEY` | One required (hosted) | — | First non-empty wins; localhost uses `"ollama"` placeholder |
| `N_PER_TASK` | No | 20 (hosted) / 5 (localhost) | Episodes per task per phase |
| `SUBMISSION_LOGS` | No | `1` | `[START]`/`[STEP]`/`[END]` on stdout |

---

## Research grounding

- **LifelongAgentBench** (2025): Multi-phase agent evaluation with adaptation and forgetting metrics across task distribution shifts.
- **Continuum Memory Architectures**: Persistent memory mechanisms to mitigate catastrophic forgetting. Our `PersistentMemory` is a minimal CMA implementation.
- **LOCOMO**: Studies what agents should remember vs forget. Task C (legacy customers) directly tests this.

**Key insight:** SaaS ops is a natural testbed for lifelong learning — policy versioning is explicit, ground truth is deterministic, and the forgetting/adaptation tradeoff has real economic meaning (wrong refund decisions cost money).

---

## Limitations

- **Simulation fidelity:** Ticket text is template-generated, not sampled from real support logs. Real tickets have more noise and ambiguity.
- **Grader scope:** Graders use keyword/substring matching, not semantic understanding. A correct answer with unusual phrasing may score lower than it deserves.
- **Scale:** Three weeks and three tasks are enough to demonstrate drift and forgetting, but a production benchmark would benefit from longer horizons and more task families.
- **Memory baseline only:** The shipped agent uses a simple heuristic (write KB summaries, read before answering). More sophisticated memory architectures (RAG, selective forgetting) are left for future work.

---

## Repository structure

```
inference.py          # Scored baseline (entry point)
server/app.py         # FastAPI OpenEnv API + browser playground
env/                  # World state, tasks, graders, KB, memory
baseline/             # LLM client + memory agent
eval/                 # Lifelong evaluation protocol + submission log format
Dockerfile            # Docker image (port 7860)
openenv.yaml          # OpenEnv typed spec
pyproject.toml        # Project metadata + [project.scripts] server
requirements.txt      # Runtime dependencies
```

---

## Contributors

- [sykeriin](https://github.com/sykeriin)
- [Palak11245](https://github.com/Palak11245)
