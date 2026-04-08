# Quick Start Guide

## Prerequisites

- Python 3.11+
- OpenAI API key
- Docker (optional, for containerized deployment)

## Local Setup (3 commands)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key
export GROQ_API_KEY=your_groq_api_key_here

# 3. Run the evaluation
python inference.py
```

## What to Expect

The evaluation will run for approximately 5-10 minutes (depending on API speed) and test the memory agent across:
- 60 tickets in Week 1 (20 per task type)
- 60 tickets in Week 2 (with policy drift)
- 60 tickets in Week 3 (with more drift)
- 60 tickets in Week 1 again (forgetting probe)

Total: 240 episodes, ~720 Groq API calls.

**Note:** Groq is generally faster than OpenAI, so evaluation may complete quicker.

## Running the Server

```bash
# Start the server
uvicorn server:app --port 8080

# In another terminal, test it
python test_server.py
```

## Docker Deployment

```bash
# Build
docker build -t lifelong-ops .

# Run
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8080:8080 lifelong-ops

# Test
curl http://localhost:8080/health
```

## Validation Checklist

Run these commands to verify everything works:

```bash
# Test 1: World state advances correctly
python -c "from env.world import advance_week, get_initial_state; s=get_initial_state(); print(advance_week(advance_week(s)).week)"
# Expected output: 3

# Test 2: Ticket generation works
python -c "from env.tasks import generate_batch; from env.world import get_initial_state; print(len(generate_batch('C', get_initial_state(), 5, 42)))"
# Expected output: 5

# Test 3: Grader works correctly
python -c "from env.grader import grade; print(grade('I approve this refund, within 30-day window', {'task_type':'B','ground_truth':{'decision':'approve','key_reason':'within 30-day refund window','correct_policy_version':'v2'},'policy_version_expected':'v2'}, None))"
# Expected output: score >= 0.8
```

## Troubleshooting

**"ModuleNotFoundError: No module named 'openai'"**
- Run: `pip install -r requirements.txt`

**"openai.AuthenticationError"**
- Check that OPENAI_API_KEY is set: `echo $OPENAI_API_KEY`
- Make sure it starts with "sk-"

**Server won't start**
- Check if port 8080 is already in use
- Try a different port: `uvicorn server:app --port 8081`

**Evaluation is slow**
- This is normal. 240 episodes × 3 LLM calls each = 720 API calls
- Use a faster model: `export MODEL_NAME=gpt-4o-mini`
- Reduce episodes: Edit `inference.py` and change `n_per_task=20` to `n_per_task=5`
