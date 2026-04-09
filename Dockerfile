FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Hugging Face Spaces (Docker SDK) expect HTTP on 7860. Local: docker run -p 7860:7860 ...
EXPOSE 7860
ENV PORT=7860
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
