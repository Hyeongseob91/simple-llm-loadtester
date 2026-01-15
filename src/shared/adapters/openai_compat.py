"""OpenAI-compatible API adapter for vLLM, SGLang, Ollama, etc."""

import json
import time
from typing import Optional

import httpx

from shared.adapters.base import BaseAdapter, AdapterFactory
from shared.core.models import RequestResult
from shared.core.tokenizer import TokenCounter


class OpenAICompatibleAdapter(BaseAdapter):
    """Adapter for OpenAI-compatible API servers.

    Supports: vLLM, SGLang, Ollama, LMDeploy, and other OpenAI API-compatible servers.
    """

    @property
    def adapter_name(self) -> str:
        return "openai"

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
        """Send a request to the OpenAI-compatible server.

        Args:
            request_id: Request identifier.
            prompt: Input prompt.
            max_tokens: Maximum tokens to generate.
            stream: Whether to use streaming.

        Returns:
            RequestResult with timing information.
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
        """Send a streaming request and measure latencies."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": True,
        }

        start_time = time.perf_counter()
        first_token_time: Optional[float] = None
        token_times: list[float] = []
        output_tokens = 0

        try:
            async with await self._create_client() as client:
                async with client.stream(
                    "POST",
                    "/v1/chat/completions",
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices and choices[0].get("delta", {}).get("content"):
                                current_time = time.perf_counter()

                                if first_token_time is None:
                                    first_token_time = current_time
                                else:
                                    token_times.append(current_time)

                                output_tokens += 1
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
                input_tokens=TokenCounter.count(prompt, self.model),  # Approximate
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
                input_tokens=TokenCounter.count(prompt, self.model),
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
                input_tokens=TokenCounter.count(prompt, self.model),
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
        """Send a non-streaming request and measure latencies."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }

        start_time = time.perf_counter()

        try:
            async with await self._create_client() as client:
                response = await client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()

                end_time = time.perf_counter()
                data = response.json()

                output_tokens = data.get("usage", {}).get("completion_tokens", 0)
                input_tokens = data.get("usage", {}).get("prompt_tokens", TokenCounter.count(prompt, self.model))

                e2e_ms = (end_time - start_time) * 1000
                ttft_ms = e2e_ms  # Non-streaming: TTFT = E2E
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
                input_tokens=TokenCounter.count(prompt, self.model),
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
                input_tokens=TokenCounter.count(prompt, self.model),
                output_tokens=0,
                success=False,
                error_type=type(e).__name__,
            )

    async def health_check(self) -> bool:
        """Check if the server is healthy and reachable."""
        try:
            async with await self._create_client() as client:
                # Try /health first (vLLM)
                response = await client.get("/health")
                if response.status_code == 200:
                    return True
        except Exception:
            pass

        try:
            async with await self._create_client() as client:
                # Try /v1/models (OpenAI standard)
                response = await client.get("/v1/models")
                return response.status_code == 200
        except Exception:
            return False


# Register the adapter
AdapterFactory.register("openai", OpenAICompatibleAdapter)
