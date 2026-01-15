"""WebSocket routes for real-time benchmark progress."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/benchmark", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for benchmark progress updates."""

    def __init__(self):
        # run_id -> set of active WebSocket connections
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection.

        Args:
            run_id: Benchmark run ID to subscribe to.
            websocket: WebSocket connection.
        """
        await websocket.accept()
        async with self._lock:
            if run_id not in self.active_connections:
                self.active_connections[run_id] = set()
            self.active_connections[run_id].add(websocket)
        logger.info(f"WebSocket connected for run {run_id[:8]}...")

    async def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            run_id: Benchmark run ID.
            websocket: WebSocket connection to remove.
        """
        async with self._lock:
            if run_id in self.active_connections:
                self.active_connections[run_id].discard(websocket)
                if not self.active_connections[run_id]:
                    del self.active_connections[run_id]
        logger.info(f"WebSocket disconnected for run {run_id[:8]}...")

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Broadcast a message to all connections for a run.

        Args:
            run_id: Benchmark run ID.
            message: Message to broadcast.
        """
        async with self._lock:
            connections = self.active_connections.get(run_id, set()).copy()

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                await self.disconnect(run_id, websocket)

    async def send_progress(
        self,
        run_id: str,
        status: str,
        current: int,
        total: int,
        concurrency_level: int,
        current_concurrency_index: int,
        total_concurrency_levels: int,
        metrics: Optional[dict] = None,
        request_log: Optional[dict] = None,
    ) -> None:
        """Send progress update to all subscribers.

        Args:
            run_id: Benchmark run ID.
            status: Current status (running, completed, failed).
            current: Current request count in this concurrency level.
            total: Total requests for this concurrency level.
            concurrency_level: Current concurrency value.
            current_concurrency_index: Index of current concurrency level (0-based).
            total_concurrency_levels: Total number of concurrency levels.
            metrics: Optional current metrics snapshot.
            request_log: Optional individual request log entry.
        """
        message = {
            "type": "progress",
            "run_id": run_id,
            "status": status,
            "progress": {
                "current": current,
                "total": total,
                "percent": round((current / total * 100) if total > 0 else 0, 1),
            },
            "concurrency": {
                "level": concurrency_level,
                "index": current_concurrency_index,
                "total": total_concurrency_levels,
            },
            "overall_percent": round(
                (
                    (current_concurrency_index * total + current)
                    / (total_concurrency_levels * total)
                    * 100
                )
                if total_concurrency_levels > 0 and total > 0
                else 0,
                1,
            ),
        }

        if metrics:
            message["metrics"] = metrics

        if request_log:
            message["request_log"] = request_log

        await self.broadcast(run_id, message)

    async def send_completed(
        self,
        run_id: str,
        summary: Optional[dict] = None,
    ) -> None:
        """Send completion notification.

        Args:
            run_id: Benchmark run ID.
            summary: Optional summary metrics.
        """
        message = {
            "type": "completed",
            "run_id": run_id,
            "status": "completed",
        }
        if summary:
            message["summary"] = summary

        await self.broadcast(run_id, message)

    async def send_failed(
        self,
        run_id: str,
        error: str,
    ) -> None:
        """Send failure notification.

        Args:
            run_id: Benchmark run ID.
            error: Error message.
        """
        await self.broadcast(
            run_id,
            {
                "type": "failed",
                "run_id": run_id,
                "status": "failed",
                "error": error,
            },
        )

    async def send_validation_log(
        self,
        run_id: str,
        step: str,
        message: str,
        status: str = "running",
    ) -> None:
        """Send validation progress log.

        Args:
            run_id: Benchmark run ID.
            step: Current validation step (init, before, after, validate, complete).
            message: Progress message.
            status: Status (running, warning, completed, failed).
        """
        await self.broadcast(
            run_id,
            {
                "type": "validation_log",
                "run_id": run_id,
                "validation_log": {
                    "step": step,
                    "message": message,
                    "status": status,
                    "timestamp": __import__("time").time(),
                },
            },
        )

    def get_connection_count(self, run_id: str) -> int:
        """Get number of active connections for a run."""
        return len(self.active_connections.get(run_id, set()))

    def get_all_connection_counts(self) -> dict[str, int]:
        """Get connection counts for all runs."""
        return {run_id: len(conns) for run_id, conns in self.active_connections.items()}


# Singleton instance
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the WebSocket connection manager instance."""
    return manager


@router.websocket("/ws/run/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for benchmark progress updates.

    Connect to receive real-time progress updates for a specific benchmark run.

    Message types:
    - progress: Periodic progress updates with current/total counts
    - completed: Sent when benchmark completes successfully
    - failed: Sent when benchmark fails

    Example message:
    ```json
    {
        "type": "progress",
        "run_id": "abc123...",
        "status": "running",
        "progress": {"current": 50, "total": 100, "percent": 50.0},
        "concurrency": {"level": 10, "index": 1, "total": 3},
        "overall_percent": 33.3
    }
    ```
    """
    await manager.connect(run_id, websocket)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message (ping/pong or close)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0,  # Ping timeout
                )

                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send ping to check if connection is alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id[:8]}...")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id[:8]}: {e}")
    finally:
        await manager.disconnect(run_id, websocket)


@router.get("/ws/stats")
async def websocket_stats() -> dict:
    """Get WebSocket connection statistics."""
    return {
        "connections": manager.get_all_connection_counts(),
        "total": sum(manager.get_all_connection_counts().values()),
    }
