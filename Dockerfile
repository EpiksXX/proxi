FROM python:3.12-slim

LABEL maintainer="EpiksXX"
LABEL description="Gemini 3 Flash Preview OpenAI Proxy"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", \
     "--worker-class", "gevent", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "300", \
     "--bind", "0.0.0.0:5000", \
     "app:app"]
