"""Base adapter interface for LLM server backends."""

from abc import ABC, abstractmethod
from typing import Optional, Type

from shared.core.models import RequestResult


class BaseAdapter(ABC):
    """Abstract base class for server adapters.

    All adapters must implement this interface to be used with the LoadGenerator.
    """

    def __init__(
        self,
        server_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """Initialize the adapter.

        Args:
            server_url: Base URL of the server.
            model: Model name to use.
            api_key: Optional API key for authentication.
            timeout: Request timeout in seconds.
        """
        self.server_url = server_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    async def send_request(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
        stream: bool,
    ) -> RequestResult:
        """Send a request to the server.

        Args:
            request_id: Unique identifier for this request.
            prompt: Input prompt text.
            max_tokens: Maximum tokens to generate.
            stream: Whether to use streaming mode.

        Returns:
            RequestResult with timing and token information.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the server is healthy and reachable.

        Returns:
            True if server is healthy, False otherwise.
        """
        pass

    async def warmup(
        self,
        num_requests: int = 3,
        input_len: int = 64,
        output_len: int = 32,
    ) -> None:
        """Run warmup requests before benchmark.

        Args:
            num_requests: Number of warmup requests.
            input_len: Input token length for warmup.
            output_len: Output token length for warmup.
        """
        prompt = "Hello, how are you? " * (input_len // 4)
        for i in range(num_requests):
            try:
                await self.send_request(i, prompt, output_len, stream=False)
            except Exception:
                pass

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Return the adapter name identifier."""
        pass


class AdapterFactory:
    """Factory for creating server adapters."""

    _adapters: dict[str, Type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[BaseAdapter]) -> None:
        """Register an adapter class.

        Args:
            name: Adapter name identifier.
            adapter_class: Adapter class to register.
        """
        cls._adapters[name] = adapter_class

    @classmethod
    def create(
        cls,
        name: str,
        server_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ) -> BaseAdapter:
        """Create an adapter instance.

        Args:
            name: Adapter name identifier.
            server_url: Server URL.
            model: Model name.
            api_key: Optional API key.
            timeout: Request timeout.

        Returns:
            Configured adapter instance.

        Raises:
            ValueError: If adapter name is not registered.
        """
        if name not in cls._adapters:
            available = list(cls._adapters.keys())
            raise ValueError(f"Unknown adapter: {name}. Available: {available}")

        adapter_class = cls._adapters[name]
        return adapter_class(
            server_url=server_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names."""
        return list(cls._adapters.keys())
