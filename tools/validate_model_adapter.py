#!/usr/bin/env python3
import json
import sys
import os

# Add parent dir to path so we can import fixture_model_adapter
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from fixture_model_adapter import compose_fixture_model
except ImportError as e:
    print(f"Failed to import adapter: {e}")
    sys.exit(1)

def validate():
    cases = [
        ("Empty list", []),
        ("All zeros", [0] * 36),
        ("All 255s", [255] * 36),
    ]

    for name, channels in cases:
        try:
            print(f"Testing {name}...")
            result = compose_fixture_model(channels)
            
            assert "decoded" in result, "Missing decoded"
            assert "composed" in result, "Missing composed"
            assert "fixture_model" in result, "Missing fixture_model"
            
            fm = result["fixture_model"]
            assert "confidence" in fm, "Missing confidence"
            assert "unsupported" in fm, "Missing unsupported"
            assert "coverage" in fm, "Missing coverage"
            
            # Check JSON serialization (like the webserver snapshot does)
            json.dumps(result)
            print(f"  {name} PASSED")
            
        except Exception as e:
            print(f"  {name} FAILED: {e}")
            sys.exit(1)

    print("All validation tests passed.")
    sys.exit(0)

if __name__ == "__main__":
    validate()
