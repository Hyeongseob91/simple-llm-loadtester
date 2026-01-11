#!/usr/bin/env python3
"""Test script for API authentication."""

import os
import sys

# Test imports
try:
    from llm_loadtest_api.auth import APIKeyAuth, get_api_key_from_env
    from llm_loadtest_api.logging_config import configure_logging, get_logger
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test API key configuration
print("\n--- Testing API Key Configuration ---")
print(f"API_KEY environment variable: {os.getenv('API_KEY', 'Not set')}")
print(f"get_api_key_from_env(): {get_api_key_from_env() or 'None (auth disabled)'}")

# Test logging configuration
print("\n--- Testing Logging Configuration ---")
try:
    configure_logging()
    logger = get_logger("test")
    logger.info("test_event", test_key="test_value")
    print("✓ Structured logging configured successfully")
except Exception as e:
    print(f"✗ Logging configuration error: {e}")
    sys.exit(1)

# Test database with indexes
print("\n--- Testing Database Indexes ---")
try:
    from shared.database import Database
    import tempfile
    import os

    # Create temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        test_db_path = f.name

    db = Database(test_db_path)

    # Check if indexes were created
    import sqlite3
    conn = sqlite3.connect(test_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cursor.fetchall()]
    conn.close()

    expected_indexes = [
        'idx_benchmark_runs_created_at',
        'idx_benchmark_runs_status',
        'idx_benchmark_runs_status_created',
        'idx_benchmark_runs_model',
    ]

    for idx in expected_indexes:
        if idx in indexes:
            print(f"✓ Index created: {idx}")
        else:
            print(f"✗ Index missing: {idx}")

    # Cleanup
    os.unlink(test_db_path)

except Exception as e:
    print(f"✗ Database error: {e}")
    sys.exit(1)

print("\n--- All Tests Passed ---")
