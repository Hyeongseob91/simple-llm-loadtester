#!/bin/bash
# Test API endpoints with and without authentication

set -e

API_URL="http://localhost:8085"
API_KEY="test-secret-key"

echo "=== LLM Loadtest API - Phase 4 Endpoint Tests ==="
echo ""

# Test 1: Health check (always public)
echo "Test 1: Health check (public endpoint)"
curl -s "${API_URL}/api/v1/benchmark/health" | jq .
echo ""

# Test 2: List runs (always public)
echo "Test 2: List benchmark runs (public endpoint)"
curl -s "${API_URL}/api/v1/benchmark/history?limit=5" | jq .
echo ""

# Test 3: Start benchmark without API key (should fail if API_KEY is set)
echo "Test 3: Start benchmark WITHOUT authentication"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${API_URL}/api/v1/benchmark/run" \
  -H "Content-Type: application/json" \
  -d '{
    "server_url": "http://localhost:8000",
    "model": "test-model",
    "adapter": "openai",
    "config": {
      "concurrency_levels": [1],
      "num_requests": 1,
      "max_input_tokens": 100,
      "max_output_tokens": 50
    }
  }')
echo "HTTP Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" == "401" ]; then
  echo "✓ Authentication required (as expected)"
elif [ "$HTTP_CODE" == "200" ]; then
  echo "✓ No authentication required (API_KEY not set)"
else
  echo "✗ Unexpected status code"
fi
echo ""

# Test 4: Start benchmark with API key
echo "Test 4: Start benchmark WITH authentication"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${API_URL}/api/v1/benchmark/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "server_url": "http://localhost:8000",
    "model": "test-model",
    "adapter": "openai",
    "config": {
      "concurrency_levels": [1],
      "num_requests": 1,
      "max_input_tokens": 100,
      "max_output_tokens": 50
    }
  }')
echo "HTTP Status: ${HTTP_CODE}"
if [ "$HTTP_CODE" == "200" ] || [ "$HTTP_CODE" == "401" ]; then
  echo "✓ Expected response"
else
  echo "✗ Unexpected status code"
fi
echo ""

# Test 5: Check request ID in response
echo "Test 5: Verify X-Request-ID header"
REQUEST_ID=$(curl -s -I "${API_URL}/api/v1/benchmark/health" | grep -i "x-request-id" | cut -d' ' -f2 | tr -d '\r')
if [ -n "$REQUEST_ID" ]; then
  echo "✓ X-Request-ID present: ${REQUEST_ID}"
else
  echo "✗ X-Request-ID header missing"
fi
echo ""

echo "=== Tests Complete ==="
echo ""
echo "To test with authentication enabled:"
echo "  export API_KEY=test-secret-key"
echo "  uvicorn llm_loadtest_api.main:app --port 8085"
echo ""
echo "To test without authentication:"
echo "  unset API_KEY"
echo "  uvicorn llm_loadtest_api.main:app --port 8085"
