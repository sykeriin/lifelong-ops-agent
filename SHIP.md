# Deploying to Hugging Face Spaces

## 1. Create the Space

1. Go to [huggingface.co](https://huggingface.co/) → **New Space**.
2. **SDK: Docker** (not Gradio). A Gradio-only Space will not expose the FastAPI API on the public URL.
3. Visibility: Public.

## 2. Push this repository into the Space

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME
# Copy all files from this repo into the Space directory.
git add -A && git commit -m "Deploy Lifelong Ops Agent (Docker)" && git push
```

Or connect your GitHub repo in the Space **Settings → Repository** tab.

## 3. Verify the deployment

Wait for the build to succeed (check the Space **Logs** tab), then:

```bash
# Health check
curl https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/health
# Expected: {"status":"healthy"}

# Reset (no body — must return 200)
curl -s -o /dev/null -w "%{http_code}" -X POST https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/reset
# Expected: 200

# OpenEnv validate (against live URL)
pip install openenv-core
openenv validate https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space
```

## 4. Run inference (local machine, not in the Space)

```bash
pip install -r requirements.txt
export API_BASE_URL=https://api.groq.com/openai/v1
export MODEL_NAME=llama-3.1-70b-versatile
export GROQ_API_KEY=your_key
export N_PER_TASK=20
python inference.py
```

Structured `[START]`/`[STEP]`/`[END]` logs go to **stdout** by default. Human-readable progress goes to **stderr**.

## Checklist

- [ ] Space SDK is **Docker** (not Gradio).
- [ ] `POST /reset` with `{}` and with no body both return **200**.
- [ ] `openenv validate <Space URL>` passes.
- [ ] `docker build` succeeds locally.
- [ ] `python inference.py` completes with scores under the 20-minute budget (hosted API + `N_PER_TASK=20`).
