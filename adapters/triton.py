"""Triton Inference Server adapter for LLM load testing.

Supports Triton Inference Server with TensorRT-LLM backend.
"""

import json
import time
from typing import Optional

import httpx

from adapters.base import BaseAdapter, AdapterFactory
from core.models import RequestResult


class TritonAdapter(BaseAdapter):
    """Adapter for Triton Inference Server.

    Supports both HTTP and gRPC protocols (HTTP implemented here).
    For TensorRT-LLM models deployed on Triton.
    """

    @property
    def adapter_name(self) -> str:
        return "triton"

    def __init__(
        self,
        server_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        super().__init__(server_url, model, api_key, timeout)
        # Triton model name and version
        self.model_name = model
        self.model_version = "1"  # Default version

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _create_client(self) -> httpx.AsyncClient:
        """Create HTTP client."""
        return httpx.AsyncClient(
            base_url=self.server_url,
            headers=self._get_headers(),
            timeout=httpx.Timeout(self.timeout),
        )

    async def send_request(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
        stream: bool,
    ) -> RequestResult:
        """Send a request to Triton Inference Server.

        Uses Triton's generate endpoint for TensorRT-LLM models.
        """
        if stream:
            return await self._send_streaming(request_id, prompt, max_tokens)
        else:
            return await self._send_non_streaming(request_id, prompt, max_tokens)

    async def _send_streaming(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
    ) -> RequestResult:
        """Send a streaming request to Triton."""
        # Triton TensorRT-LLM generate endpoint format
        payload = {
            "text_input": prompt,
            "max_tokens": max_tokens,
            "stream": True,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        start_time = time.perf_counter()
        first_token_time: Optional[float] = None
        token_times: list[float] = []
        output_tokens = 0
        output_text = ""

        try:
            async with await self._create_client() as client:
                # Triton streaming endpoint
                endpoint = f"/v2/models/{self.model_name}/generate_stream"

                async with client.stream(
                    "POST",
                    endpoint,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # Triton returns JSON objects, one per line
                        try:
                            data = json.loads(line)
                            text_output = data.get("text_output", "")

                            if text_output:
                                current_time = time.perf_counter()

                                if first_token_time is None:
                                    first_token_time = current_time
                                else:
                                    token_times.append(current_time)

                                # Count new tokens (approximate by word/space)
                                new_text = text_output[len(output_text):]
                                output_tokens += len(new_text.split())
                                output_text = text_output

                        except json.JSONDecodeError:
                            continue

            end_time = time.perf_counter()

            if first_token_time is None:
                first_token_time = end_time

            ttft_ms = (first_token_time - start_time) * 1000
            e2e_ms = (end_time - start_time) * 1000

            tpot_ms: Optional[float] = None
            itl_ms: Optional[list[float]] = None

            if output_tokens > 1:
                tpot_ms = (end_time - first_token_time) * 1000 / (output_tokens - 1)

            if len(token_times) > 1:
                itl_ms = [
                    (token_times[i] - token_times[i - 1]) * 1000
                    for i in range(1, len(token_times))
                ]

            return RequestResult(
                request_id=request_id,
                ttft_ms=ttft_ms,
                tpot_ms=tpot_ms,
                e2e_latency_ms=e2e_ms,
                input_tokens=len(prompt.split()),
                output_tokens=output_tokens,
                success=True,
                itl_ms=itl_ms,
            )

        except httpx.HTTPStatusError as e:
            end_time = time.perf_counter()
            return RequestResult(
                request_id=request_id,
                ttft_ms=0,
                e2e_latency_ms=(end_time - start_time) * 1000,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                success=False,
                error_type=f"HTTP_{e.response.status_code}",
            )
        except Exception as e:
            end_time = time.perf_counter()
            return RequestResult(
                request_id=request_id,
                ttft_ms=0,
                e2e_latency_ms=(end_time - start_time) * 1000,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                success=False,
                error_type=type(e).__name__,
            )

    async def _send_non_streaming(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
    ) -> RequestResult:
        """Send a non-streaming request to Triton."""
        payload = {
            "text_input": prompt,
            "max_tokens": max_tokens,
            "stream": False,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        start_time = time.perf_counter()

        try:
            async with await self._create_client() as client:
                # Triton generate endpoint
                endpoint = f"/v2/models/{self.model_name}/generate"
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()

                end_time = time.perf_counter()
                data = response.json()

                text_output = data.get("text_output", "")
                output_tokens = len(text_output.split())
                input_tokens = len(prompt.split())

                e2e_ms = (end_time - start_time) * 1000
                ttft_ms = e2e_ms
                tpot_ms = e2e_ms / output_tokens if output_tokens > 0 else None

                return RequestResult(
                    request_id=request_id,
                    ttft_ms=ttft_ms,
                    tpot_ms=tpot_ms,
                    e2e_latency_ms=e2e_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=True,
                )

        except httpx.HTTPStatusError as e:
            end_time = time.perf_counter()
            return RequestResult(
                request_id=request_id,
                ttft_ms=0,
                e2e_latency_ms=(end_time - start_time) * 1000,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                success=False,
                error_type=f"HTTP_{e.response.status_code}",
            )
        except Exception as e:
            end_time = time.perf_counter()
            return RequestResult(
                request_id=request_id,
                ttft_ms=0,
                e2e_latency_ms=(end_time - start_time) * 1000,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                success=False,
                error_type=type(e).__name__,
            )

    async def health_check(self) -> bool:
        """Check if Triton server is healthy."""
        try:
            async with await self._create_client() as client:
                # Triton health endpoint
                response = await client.get("/v2/health/ready")
                return response.status_code == 200
        except Exception:
            return False

        # Also check model status
        try:
            async with await self._create_client() as client:
                response = await client.get(f"/v2/models/{self.model_name}/ready")
                return response.status_code == 200
        except Exception:
            return False


# Register the adapter
AdapterFactory.register("triton", TritonAdapter)
