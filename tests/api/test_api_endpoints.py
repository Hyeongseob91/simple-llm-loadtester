"""API endpoint tests using FastAPI TestClient."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Add parent path for imports
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "src" / "services" / "api" / "src"))

from llm_loadtest_api.main import create_app
from llm_loadtest_api.routers import benchmarks


@pytest.fixture
def mock_service():
    """Create mock benchmark service."""
    service = MagicMock()
    service.start_benchmark = AsyncMock(return_value="test-run-id-123")
    service.get_status.return_value = None
    service.get_result.return_value = None
    service.list_runs.return_value = []
    service.delete_run.return_value = False
    service.compare_runs.return_value = {}
    return service


@pytest.fixture
def app(mock_service):
    """Create test application with mocked service."""
    test_app = create_app()

    # Reset global state in benchmarks router
    benchmarks._db = None
    benchmarks._service = None

    # Override the get_service dependency
    def override_get_service():
        return mock_service

    test_app.dependency_overrides[benchmarks.get_service] = override_get_service
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def client_with_auth(app, api_key):
    """Create test client with API key authentication enabled."""
    with patch.dict(os.environ, {"API_KEY": api_key}):
        yield TestClient(app), api_key


class TestRootEndpoints:
    """Tests for root-level endpoints."""

    def test_root_returns_service_info(self, client):
        """Test that root endpoint returns service information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "llm-loadtest-api"
        assert "version" in data
        assert data["docs"] == "/docs"

    def test_health_returns_healthy(self, client):
        """Test that /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestBenchmarkHealthEndpoint:
    """Tests for /api/v1/benchmark/health endpoint."""

    def test_health_check_returns_healthy(self, client):
        """Test benchmark health endpoint."""
        response = client.get("/api/v1/benchmark/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestBenchmarkRunEndpoint:
    """Tests for /api/v1/benchmark/run endpoint."""

    def test_run_requires_api_key(self, client_with_auth):
        """Test that POST /run requires API key when configured."""
        client, api_key = client_with_auth

        # Without API key - should fail
        response = client.post(
            "/api/v1/benchmark/run",
            json={
                "server_url": "http://localhost:8000",
                "model": "test-model",
            },
        )
        assert response.status_code == 401

    def test_run_with_valid_api_key(self, app, mock_service, api_key):
        """Test that POST /run works with valid API key."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.post(
                "/api/v1/benchmark/run",
                json={
                    "server_url": "http://localhost:8000",
                    "model": "test-model",
                    "adapter": "openai",
                    "concurrency": [1, 10],
                    "num_prompts": 50,
                },
                headers={"X-API-Key": api_key},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == "test-run-id-123"
            assert data["status"] == "started"
            mock_service.start_benchmark.assert_called_once()

    def test_run_without_auth_when_not_configured(self, app, mock_service):
        """Test that POST /run works without API key when not configured."""
        # No API_KEY environment variable set
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            client = TestClient(app)

            response = client.post(
                "/api/v1/benchmark/run",
                json={
                    "server_url": "http://localhost:8000",
                    "model": "test-model",
                },
            )

            assert response.status_code == 200


class TestBenchmarkStatusEndpoint:
    """Tests for /api/v1/benchmark/run/{run_id} endpoint."""

    def test_get_status_returns_run_info(self, app, mock_service):
        """Test GET /run/{run_id} returns status."""
        mock_service.get_status.return_value = {
            "id": "test-run-id",
            "status": "running",
            "server_url": "http://localhost:8000",
            "model": "test-model",
            "adapter": "openai",
            "started_at": datetime.now(),
            "completed_at": None,
            "created_at": datetime.now(),
        }

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/run/test-run-id")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "test-run-id"
        assert data["status"] == "running"
        assert data["model"] == "test-model"

    def test_get_status_returns_404_for_missing_run(self, app, mock_service):
        """Test GET /run/{run_id} returns 404 for non-existent run."""
        mock_service.get_status.return_value = None

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/run/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestBenchmarkResultEndpoint:
    """Tests for /api/v1/benchmark/result/{run_id} endpoint."""

    def test_get_result_returns_completed_result(self, app, mock_service):
        """Test GET /result/{run_id} returns result for completed run."""
        mock_result = {
            "run_id": "test-run-id",
            "model": "test-model",
            "server_url": "http://localhost:8000",
            "adapter": "openai",
            "results": [
                {
                    "concurrency": 1,
                    "throughput_tokens_per_sec": 500.0,
                    "ttft": {"p50": 100, "p95": 150, "p99": 200},
                }
            ],
            "summary": {"best_throughput": 500.0},
        }
        mock_service.get_result.return_value = mock_result

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/result/test-run-id")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "test-run-id"
        assert data["results"][0]["concurrency"] == 1

    def test_get_result_returns_404_for_missing_run(self, app, mock_service):
        """Test GET /result/{run_id} returns 404 for non-existent run."""
        mock_service.get_result.return_value = None
        mock_service.get_status.return_value = None

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/result/non-existent-id")

        assert response.status_code == 404

    def test_get_result_returns_202_for_running(self, app, mock_service):
        """Test GET /result/{run_id} returns 202 for still-running benchmark."""
        mock_service.get_result.return_value = None
        mock_service.get_status.return_value = {
            "id": "test-run-id",
            "status": "running",
        }

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/result/test-run-id")

        assert response.status_code == 202
        assert "still running" in response.json()["detail"].lower()

    def test_get_result_returns_500_for_failed(self, app, mock_service):
        """Test GET /result/{run_id} returns 500 for failed benchmark."""
        mock_service.get_result.return_value = None
        mock_service.get_status.return_value = {
            "id": "test-run-id",
            "status": "failed",
        }

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/result/test-run-id")

        assert response.status_code == 500


class TestBenchmarkHistoryEndpoint:
    """Tests for /api/v1/benchmark/history endpoint."""

    def test_list_runs_returns_empty_list(self, app, mock_service):
        """Test GET /history returns empty list when no runs."""
        mock_service.list_runs.return_value = []

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/history")

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_list_runs_with_pagination(self, app, mock_service):
        """Test GET /history with pagination parameters."""
        mock_service.list_runs.return_value = [
            {
                "id": f"run-{i}",
                "status": "completed",
                "server_url": "http://localhost:8000",
                "model": "test-model",
                "adapter": "openai",
                "created_at": datetime.now(),
            }
            for i in range(10)
        ]

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/history?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 10
        assert data["limit"] == 10
        assert data["offset"] == 0


class TestBenchmarkDeleteEndpoint:
    """Tests for DELETE /api/v1/benchmark/run/{run_id} endpoint."""

    def test_delete_requires_api_key(self, client_with_auth):
        """Test that DELETE /run/{run_id} requires API key."""
        client, api_key = client_with_auth

        # Without API key
        response = client.delete("/api/v1/benchmark/run/test-run-id")
        assert response.status_code == 401

    def test_delete_with_valid_api_key(self, app, mock_service, api_key):
        """Test DELETE /run/{run_id} with valid API key."""
        mock_service.delete_run.return_value = True

        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.delete(
                "/api/v1/benchmark/run/test-run-id",
                headers={"X-API-Key": api_key},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] == "test-run-id"

    def test_delete_returns_404_for_missing_run(self, app, mock_service, api_key):
        """Test DELETE /run/{run_id} returns 404 for non-existent run."""
        mock_service.delete_run.return_value = False

        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.delete(
                "/api/v1/benchmark/run/non-existent-id",
                headers={"X-API-Key": api_key},
            )

            assert response.status_code == 404


class TestBenchmarkCompareEndpoint:
    """Tests for POST /api/v1/benchmark/compare endpoint."""

    def test_compare_runs(self, app, mock_service):
        """Test POST /compare returns comparison."""
        mock_service.compare_runs.return_value = {
            "runs": [],
            "comparison": {
                "best_throughput": {"run_id": "run-1", "value": 1000.0},
            },
        }

        client = TestClient(app)
        response = client.post(
            "/api/v1/benchmark/compare",
            json={"run_ids": ["run-1", "run-2"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "comparison" in data


class TestBenchmarkExportEndpoint:
    """Tests for GET /api/v1/benchmark/result/{run_id}/export endpoint."""

    def test_export_csv(self, app, mock_service):
        """Test CSV export."""
        mock_result = {
            "run_id": "test-run-id",
            "model": "test-model",
            "server_url": "http://localhost:8000",
            "adapter": "openai",
            "started_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:10:00",
            "duration_seconds": 600,
            "results": [],
            "summary": {},
        }
        mock_service.get_result.return_value = mock_result

        client = TestClient(app)
        response = client.get("/api/v1/benchmark/result/test-run-id/export?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]


class TestRecommendEndpoint:
    """Tests for /api/v1/benchmark/recommend endpoints."""

    def test_recommend_requires_api_key(self, api_key):
        """Test that POST /recommend requires API key."""
        app = create_app()
        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.post(
                "/api/v1/benchmark/recommend",
                json={
                    "server_url": "http://localhost:8000",
                    "model": "test-model",
                    "workload": {
                        "peak_concurrency": 100,
                        "avg_input_tokens": 256,
                        "avg_output_tokens": 512,
                    },
                },
            )
            assert response.status_code == 401

    def test_get_recommend_status_returns_404(self, client):
        """Test GET /recommend/{run_id} returns 404 for non-existent run."""
        response = client.get("/api/v1/benchmark/recommend/non-existent-id")
        assert response.status_code == 404

    def test_get_recommend_result_returns_404(self, client):
        """Test GET /recommend/{run_id}/result returns 404 for non-existent run."""
        response = client.get("/api/v1/benchmark/recommend/non-existent-id/result")
        assert response.status_code == 404


class TestAuthentication:
    """Tests for API authentication."""

    def test_invalid_api_key_returns_401(self, app, api_key):
        """Test that invalid API key returns 401."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.post(
                "/api/v1/benchmark/run",
                json={
                    "server_url": "http://localhost:8000",
                    "model": "test-model",
                },
                headers={"X-API-Key": "wrong-api-key"},
            )
            assert response.status_code == 401

    def test_missing_api_key_returns_401(self, app, api_key):
        """Test that missing API key returns 401 when configured."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            client = TestClient(app)

            response = client.post(
                "/api/v1/benchmark/run",
                json={
                    "server_url": "http://localhost:8000",
                    "model": "test-model",
                },
                # No X-API-Key header
            )
            assert response.status_code == 401


class TestRequestValidation:
    """Tests for request validation."""

    def test_run_requires_server_url(self, client):
        """Test that POST /run requires server_url."""
        response = client.post(
            "/api/v1/benchmark/run",
            json={"model": "test-model"},
        )
        assert response.status_code == 422  # Validation error

    def test_run_requires_model(self, client):
        """Test that POST /run requires model."""
        response = client.post(
            "/api/v1/benchmark/run",
            json={"server_url": "http://localhost:8000"},
        )
        assert response.status_code == 422  # Validation error

    def test_compare_requires_at_least_2_runs(self, client):
        """Test that POST /compare requires at least 2 run_ids."""
        response = client.post(
            "/api/v1/benchmark/compare",
            json={"run_ids": ["only-one"]},
        )
        assert response.status_code == 422

    def test_compare_requires_at_most_5_runs(self, client):
        """Test that POST /compare requires at most 5 run_ids."""
        response = client.post(
            "/api/v1/benchmark/compare",
            json={"run_ids": ["run-1", "run-2", "run-3", "run-4", "run-5", "run-6"]},
        )
        assert response.status_code == 422
