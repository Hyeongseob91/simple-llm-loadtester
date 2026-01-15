FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn>=0.24.0 \
    pydantic>=2.0.0 \
    httpx>=0.25.0 \
    aiohttp>=3.9.0 \
    numpy>=1.24.0 \
    openpyxl>=3.1.0 \
    websockets>=12.0 \
    tiktoken>=0.5.0 \
    structlog>=23.0.0 \
    psutil>=5.9.0 \
    nvidia-ml-py>=12.0.0

# Copy source
COPY shared/core/ /app/shared/core/
COPY shared/adapters/ /app/shared/adapters/
COPY shared/database/ /app/shared/database/
COPY services/api/src/llm_loadtest_api/ /app/llm_loadtest_api/

# Create data directory
RUN mkdir -p /data

ENV PYTHONPATH=/app
ENV DATABASE_PATH=/data/benchmarks.db
ENV PORT=8085

EXPOSE 8085

CMD ["sh", "-c", "uvicorn llm_loadtest_api.main:app --host 0.0.0.0 --port ${PORT}"]
