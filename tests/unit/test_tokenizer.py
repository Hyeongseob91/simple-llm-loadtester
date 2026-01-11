"""Unit tests for TokenCounter utility."""

import pytest

from shared.core.tokenizer import TokenCounter


class TestTokenCounter:
    """Tests for TokenCounter class."""

    class TestIsAvailable:
        """Tests for is_available method."""

        def test_tiktoken_availability(self):
            """Test that tiktoken availability is correctly reported."""
            # Should return True if tiktoken is installed, False otherwise
            available = TokenCounter.is_available()
            assert isinstance(available, bool)

    class TestCount:
        """Tests for count method."""

        def test_count_simple_text(self):
            """Test token counting for simple English text."""
            text = "Hello, how are you?"
            count = TokenCounter.count(text)
            assert count > 0
            # Simple English text should be roughly 5-6 tokens
            assert 3 <= count <= 10

        def test_count_empty_text(self):
            """Test token counting for empty text."""
            count = TokenCounter.count("")
            assert count >= 0

        def test_count_long_text(self):
            """Test token counting for longer text."""
            text = "This is a longer text that should have more tokens. " * 10
            count = TokenCounter.count(text)
            assert count > 50  # Should have many tokens

        def test_count_code(self):
            """Test token counting for code."""
            code = """
def hello_world():
    print("Hello, World!")
    return True
"""
            count = TokenCounter.count(code)
            assert count > 0

        def test_count_special_characters(self):
            """Test token counting with special characters."""
            text = "Special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"
            count = TokenCounter.count(text)
            assert count > 0

        def test_count_unicode(self):
            """Test token counting with unicode characters."""
            text = "Unicode: 你好世界 🎉 émojis"
            count = TokenCounter.count(text)
            assert count > 0

        def test_count_with_different_models(self):
            """Test token counting with different model names."""
            text = "Test text for token counting"

            # All should work and return positive counts
            for model in ["gpt-4", "gpt-3.5-turbo", "qwen-14b", "llama-7b", "unknown-model"]:
                count = TokenCounter.count(text, model=model)
                assert count > 0

    class TestCountApproximate:
        """Tests for count_approximate method."""

        def test_approximate_count_basic(self):
            """Test approximate token counting."""
            text = "This is a test sentence with several words."
            count = TokenCounter.count_approximate(text)
            assert count > 0

        def test_approximate_minimum_one(self):
            """Test that approximate count is at least 1 for non-empty text."""
            text = "Hi"
            count = TokenCounter.count_approximate(text)
            assert count >= 1

        def test_approximate_empty(self):
            """Test approximate count for empty string."""
            count = TokenCounter.count_approximate("")
            # Should return at least 0 or 1 based on implementation
            assert count >= 0

        def test_approximate_long_text(self):
            """Test approximate count scales with text length."""
            short_text = "Short text"
            long_text = "This is a much longer text that should have significantly more tokens estimated"

            short_count = TokenCounter.count_approximate(short_text)
            long_count = TokenCounter.count_approximate(long_text)

            assert long_count > short_count

    class TestEncode:
        """Tests for encode method."""

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_encode_basic(self):
            """Test encoding text to token IDs."""
            text = "Hello world"
            tokens = TokenCounter.encode(text)
            assert isinstance(tokens, list)
            assert len(tokens) > 0
            assert all(isinstance(t, int) for t in tokens)

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_encode_empty(self):
            """Test encoding empty text."""
            tokens = TokenCounter.encode("")
            assert isinstance(tokens, list)
            assert len(tokens) == 0

        def test_encode_without_tiktoken(self):
            """Test encode returns empty list without tiktoken."""
            # This test should work regardless of tiktoken availability
            tokens = TokenCounter.encode("test")
            assert isinstance(tokens, list)

    class TestDecode:
        """Tests for decode method."""

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_decode_basic(self):
            """Test decoding token IDs to text."""
            text = "Hello world"
            tokens = TokenCounter.encode(text)
            decoded = TokenCounter.decode(tokens)
            assert decoded == text

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_decode_empty(self):
            """Test decoding empty token list."""
            decoded = TokenCounter.decode([])
            assert decoded == ""

        def test_decode_without_tiktoken(self):
            """Test decode returns empty string without tiktoken."""
            decoded = TokenCounter.decode([1, 2, 3])
            assert isinstance(decoded, str)

    class TestGetEncoder:
        """Tests for get_encoder method."""

        def test_get_encoder_returns_encoder_or_none(self):
            """Test that get_encoder returns encoder or None."""
            encoder = TokenCounter.get_encoder("gpt-4")
            # Should be either a tiktoken Encoding object or None
            if TokenCounter.is_available():
                assert encoder is not None
            else:
                assert encoder is None

        def test_get_encoder_caches_encoders(self):
            """Test that encoders are cached."""
            # Get encoder twice for same model
            encoder1 = TokenCounter.get_encoder("gpt-4")
            encoder2 = TokenCounter.get_encoder("gpt-4")

            # Should be the same object (cached)
            if TokenCounter.is_available():
                assert encoder1 is encoder2

        def test_get_encoder_different_models(self):
            """Test getting encoders for different model families."""
            models = ["qwen-14b", "llama-7b", "mistral-7b", "deepseek-v2"]

            for model in models:
                encoder = TokenCounter.get_encoder(model)
                if TokenCounter.is_available():
                    assert encoder is not None

    class TestRoundTrip:
        """Tests for encode/decode round-trip."""

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_roundtrip_simple(self):
            """Test that encode/decode is reversible for simple text."""
            original = "Hello, how are you today?"
            tokens = TokenCounter.encode(original)
            decoded = TokenCounter.decode(tokens)
            assert decoded == original

        @pytest.mark.skipif(
            not TokenCounter.is_available(),
            reason="tiktoken not installed"
        )
        def test_roundtrip_complex(self):
            """Test roundtrip with more complex text."""
            original = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
            tokens = TokenCounter.encode(original)
            decoded = TokenCounter.decode(tokens)
            assert decoded == original

    class TestConsistency:
        """Tests for counting consistency."""

        def test_count_consistency(self):
            """Test that same text always returns same count."""
            text = "This is a test for consistency"
            counts = [TokenCounter.count(text) for _ in range(5)]
            assert all(c == counts[0] for c in counts)

        def test_count_matches_encode_length(self):
            """Test that count equals length of encoded tokens."""
            if not TokenCounter.is_available():
                pytest.skip("tiktoken not installed")

            text = "Testing count vs encode length"
            count = TokenCounter.count(text)
            tokens = TokenCounter.encode(text)
            assert count == len(tokens)
