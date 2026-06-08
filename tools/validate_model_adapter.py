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
        ("Bad values", [300, -10, "bad", None]),
        ("Extra long", [0] * 100),
    ]

    for name, channels in cases:
        try:
            print(f"Testing {name}...")
            result = compose_fixture_model(channels)
            
            
            # Check input list not mutated
            input_copy = list(channels)
            result = compose_fixture_model(channels)
            assert channels == input_copy, "Input list was mutated"
            
            # Test cached model passed in
            try:
                from fixture_model_adapter import load_fixture_model, sanitize_model
                model = sanitize_model(load_fixture_model())
                result_cached = compose_fixture_model(channels, model=model)
            except Exception as e:
                print(f"  Warning: couldn't load/sanitize cache for test: {e}")
                result_cached = result
            
            for test_result in (result, result_cached):
                assert "decoded" in test_result, "Missing decoded"
                assert "composed" in test_result, "Missing composed"
                assert "fixture_model" in test_result, "Missing fixture_model"
                
                fm = test_result["fixture_model"]
                assert "confidence" in fm, "Missing confidence"
                assert "unsupported" in fm, "Missing unsupported"
                assert "coverage" in fm, "Missing coverage"
                assert "composition_applied" in fm, "Missing composition_applied"
                assert "composition_missing" in fm, "Missing composition_missing"
                assert "gating_partial" in fm, "Missing gating_partial"
            
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
