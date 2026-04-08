FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
ENV GROQ_API_KEY=""
ENV MODEL_NAME="llama-3.1-70b-versatile"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
