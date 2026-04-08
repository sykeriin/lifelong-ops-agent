# Deployment Guide

## HuggingFace Spaces

### Option 1: Direct Upload

1. Create a new Space on HuggingFace
2. Choose "Gradio" as the SDK
3. Upload all files from this repository
4. Add your OpenAI API key as a Space secret:
   - Go to Settings → Repository secrets
   - Add `OPENAI_API_KEY` with your key
5. The Space will auto-deploy using `app.py`

### Option 2: Git Push

```bash
# Clone your Space repo
git clone https://huggingface.co/spaces/YOUR_USERNAME/lifelong-ops-agent
cd lifelong-ops-agent

# Copy all files
cp -r /path/to/this/repo/* .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

### Space Configuration

Create a `README.md` in your Space with this header:

```yaml
---
title: Lifelong Ops Agent Benchmark
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
---
```

## Docker Deployment

### Local Docker

```bash
# Build
docker build -t lifelong-ops .

# Run with API key
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8080:8080 lifelong-ops

# Test
curl http://localhost:8080/health
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  lifelong-ops:
    build: .
    ports:
      - "8080:8080"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MODEL_NAME=gpt-4o-mini
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

### Cloud Deployment

#### AWS ECS

1. Push image to ECR:
```bash
aws ecr create-repository --repository-name lifelong-ops
docker tag lifelong-ops:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/lifelong-ops:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/lifelong-ops:latest
```

2. Create ECS task definition with environment variable `OPENAI_API_KEY`
3. Deploy as ECS service

#### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/lifelong-ops

# Deploy
gcloud run deploy lifelong-ops \
  --image gcr.io/YOUR_PROJECT/lifelong-ops \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=$OPENAI_API_KEY
```

#### Azure Container Instances

```bash
az container create \
  --resource-group myResourceGroup \
  --name lifelong-ops \
  --image YOUR_REGISTRY.azurecr.io/lifelong-ops:latest \
  --dns-name-label lifelong-ops \
  --ports 8080 \
  --environment-variables OPENAI_API_KEY=$OPENAI_API_KEY
```

## Production Considerations

### Security

1. **Never commit API keys** - Use environment variables or secrets management
2. **Rate limiting** - Add rate limiting to prevent abuse:
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   ```
3. **Authentication** - Add API key authentication for production use

### Monitoring

Add logging and metrics:

```python
import logging
logging.basicConfig(level=logging.INFO)

@app.middleware("http")
async def log_requests(request, call_next):
    logging.info(f"{request.method} {request.url}")
    response = await call_next(request)
    return response
```

### Scaling

- Use Redis for shared memory across instances
- Add load balancer for multiple replicas
- Consider async OpenAI calls for better throughput

### Cost Optimization

- Use `gpt-4o-mini` instead of `gpt-4` (10x cheaper)
- Cache KB search results
- Implement request batching
- Set max tokens limit on OpenAI calls

## Troubleshooting

**Container won't start**
- Check logs: `docker logs <container_id>`
- Verify API key is set: `docker exec <container_id> env | grep OPENAI`

**Out of memory**
- Increase container memory limit
- Reduce batch size in evaluation

**Slow responses**
- Use faster model (gpt-4o-mini)
- Enable response streaming
- Add caching layer

**API rate limits**
- Add exponential backoff
- Use multiple API keys with round-robin
- Reduce concurrent requests
