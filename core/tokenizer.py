"""Token counting utility using tiktoken."""

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Lazy import to avoid import errors if tiktoken is not installed
_tiktoken = None
_encoders: dict[str, "tiktoken.Encoding"] = {}


def _get_tiktoken():
    """Lazy load tiktoken module."""
    global _tiktoken
    if _tiktoken is None:
        try:
            import tiktoken
            _tiktoken = tiktoken
        except ImportError:
            logger.warning(
                "tiktoken not installed. Using approximate token counting. "
                "Install with: pip install tiktoken"
            )
            _tiktoken = False
    return _tiktoken


class TokenCounter:
    """Token counting utility using tiktoken.

    Supports OpenAI models and falls back to approximate counting
    for unknown models or when tiktoken is not installed.
    """

    # Model to encoding mapping for non-OpenAI models
    MODEL_ENCODING_MAP = {
        # Qwen models use similar tokenization to GPT-4
        "qwen": "cl100k_base",
        "llama": "cl100k_base",
        "mistral": "cl100k_base",
        "deepseek": "cl100k_base",
        # Default for unknown models
        "default": "cl100k_base",
    }

    @classmethod
    def get_encoder(cls, model: str) -> Optional["tiktoken.Encoding"]:
        """Get or create tiktoken encoder for model.

        Args:
            model: Model name (e.g., "gpt-4", "qwen-14b")

        Returns:
            tiktoken Encoding or None if tiktoken not available.
        """
        tiktoken = _get_tiktoken()
        if not tiktoken:
            return None

        if model not in _encoders:
            try:
                # Try exact model name first (works for OpenAI models)
                _encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Find matching encoding from known model families
                model_lower = model.lower()
                encoding_name = cls.MODEL_ENCODING_MAP["default"]

                for prefix, enc in cls.MODEL_ENCODING_MAP.items():
                    if prefix in model_lower:
                        encoding_name = enc
                        break

                _encoders[model] = tiktoken.get_encoding(encoding_name)

        return _encoders[model]

    @classmethod
    def count(cls, text: str, model: str = "gpt-4") -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for.
            model: Model name for tokenizer selection.

        Returns:
            Token count.
        """
        encoder = cls.get_encoder(model)
        if encoder:
            return len(encoder.encode(text))
        return cls.count_approximate(text)

    @classmethod
    def count_approximate(cls, text: str) -> int:
        """Approximate token count (fallback when tiktoken unavailable).

        Uses the heuristic that ~4 characters = 1 token for English text.
        This is less accurate for non-English text or code.

        Args:
            text: Text to count tokens for.

        Returns:
            Approximate token count.
        """
        # More accurate approximation using multiple heuristics
        char_count = len(text)
        word_count = len(text.split())

        # Average of char-based and word-based estimates
        # ~4 chars per token, ~0.75 words per token (1.33 tokens per word)
        char_estimate = char_count // 4
        word_estimate = int(word_count * 1.33)

        return max(1, (char_estimate + word_estimate) // 2)

    @classmethod
    def encode(cls, text: str, model: str = "gpt-4") -> list[int]:
        """Encode text to token IDs.

        Args:
            text: Text to encode.
            model: Model name for tokenizer selection.

        Returns:
            List of token IDs (empty if tiktoken unavailable).
        """
        encoder = cls.get_encoder(model)
        if encoder:
            return encoder.encode(text)
        return []

    @classmethod
    def decode(cls, tokens: list[int], model: str = "gpt-4") -> str:
        """Decode token IDs to text.

        Args:
            tokens: Token IDs to decode.
            model: Model name for tokenizer selection.

        Returns:
            Decoded text (empty if tiktoken unavailable).
        """
        encoder = cls.get_encoder(model)
        if encoder:
            return encoder.decode(tokens)
        return ""

    @classmethod
    def is_available(cls) -> bool:
        """Check if tiktoken is available."""
        return bool(_get_tiktoken())
