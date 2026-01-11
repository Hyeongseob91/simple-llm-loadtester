# LLM Loadtest API

FastAPI backend for running and managing LLM server load tests.

## Features

- RESTful API for benchmark management
- WebSocket support for real-time progress updates
- API key authentication (optional)
- Structured JSON logging with request ID tracking
- CSV/Excel export functionality
- Database indexing for optimal query performance

## Quick Start

### Installation

```bash
cd api
pip install -e .
```

### Running the Server

```bash
# Without authentication
uvicorn llm_loadtest_api.main:app --host 0.0.0.0 --port 8085

# With authentication
export API_KEY=your-secret-key
uvicorn llm_loadtest_api.main:app --host 0.0.0.0 --port 8085
```

### Docker

```bash
# Build
docker build -f docker/Dockerfile.api -t llm-loadtest-api .

# Run without authentication
docker run -p 8085:8085 -v $(pwd)/data:/data llm-loadtest-api

# Run with authentication
docker run -p 8085:8085 -v $(pwd)/data:/data \
  -e API_KEY=your-secret-key \
  llm-loadtest-api
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8085/docs
- ReDoc: http://localhost:8085/redoc

## Authentication

API key authentication is **optional** and configured via the `API_KEY` environment variable.

### Behavior

- **If `API_KEY` is not set**: All endpoints are publicly accessible (development mode)
- **If `API_KEY` is set**: Write operations require authentication

### Protected Endpoints

When authentication is enabled, these endpoints require the `X-API-Key` header:

- `POST /api/v1/benchmark/run` - Start a new benchmark
- `DELETE /api/v1/benchmark/run/{run_id}` - Delete a benchmark run

### Public Endpoints (Always Accessible)

- `GET /api/v1/benchmark/health` - Health check
- `GET /api/v1/benchmark/run/{run_id}` - Get run status
- `GET /api/v1/benchmark/result/{run_id}` - Get benchmark result
- `GET /api/v1/benchmark/history` - List runs
- `GET /api/v1/benchmark/result/{run_id}/export` - Export result
- `POST /api/v1/benchmark/compare` - Compare runs
- `WS /ws/benchmark/{run_id}` - WebSocket progress updates

### Usage Example

```bash
# Start a benchmark with authentication
curl -X POST http://localhost:8085/api/v1/benchmark/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{
    "server_url": "http://localhost:8000",
    "model": "meta-llama/Llama-3.2-3B-Instruct",
    "adapter": "openai",
    "config": {
      "concurrency_levels": [1, 2, 4],
      "num_requests": 10,
      "max_input_tokens": 512,
      "max_output_tokens": 128
    }
  }'

# Get results (no authentication required)
curl http://localhost:8085/api/v1/benchmark/result/{run_id}
```

## Logging

The API uses **structured logging** with JSON output for easy parsing and monitoring.

### Log Format

```json
{
  "event": "request_started",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/v1/benchmark/run",
  "client_ip": "127.0.0.1",
  "timestamp": "2025-01-10T12:00:00.123456Z",
  "log_level": "info"
}
```

### Request Tracking

Every request is assigned a unique `request_id` that:
- Appears in all logs for that request
- Is included in the response headers as `X-Request-ID`
- Can be used to trace requests across services

### Benchmark Events

Special events are logged for benchmark operations:

- `benchmark_started` - When a benchmark begins
- `benchmark_completed` - When a benchmark finishes successfully
- `benchmark_failed` - When a benchmark encounters an error
- `benchmark_deleted` - When a benchmark run is deleted

## Database

The API uses SQLite with optimized indexing for performance.

### Indexes

The following indexes are automatically created:

- `idx_benchmark_runs_created_at` - Chronological queries (DESC)
- `idx_benchmark_runs_status` - Status filtering
- `idx_benchmark_runs_status_created` - Combined status + time queries
- `idx_benchmark_runs_model` - Model filtering

### Database Location

Default: `benchmarks.db` in the current directory

Override with environment variable:
```bash
export DATABASE_PATH=/path/to/benchmarks.db
```

## Configuration

See `.env.example` for all available configuration options.

## Development

### Install with dev dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

## Phase 4: Production Ready Features

This release includes:

1. **API Key Authentication** - Optional X-API-Key header protection for write operations
2. **Structured Logging** - JSON logs with request ID tracking using structlog
3. **Database Indexing** - Optimized queries for status, created_at, and model columns
4. **Request Tracking** - Unique request IDs for debugging and monitoring

## License

MIT
