"""Quick test runner with summary"""
import sys
sys.path.insert(0, r'c:\Users\P12B91B\OneDrive - Ceridian HCM Inc\Desktop\AI-Rag Engine\ai-engine')

import unittest

loader = unittest.TestLoader()
suite = loader.discover('.')
runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

print(f"\n{'='*70}")
print(f"SUMMARY:")
print(f"  Tests run: {result.testsRun}")
print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
print(f"  Failures: {len(result.failures)}")
print(f"  Errors: {len(result.errors)}")
print(f"  Skipped: {len(result.skipped)}")
print(f"{'='*70}")

if result.failures:
    print("\nFAILURES:")
    for test, trace in result.failures[:5]:  # Show first 5
        print(f"  - {test}")

if result.errors:
    print("\nERRORS:")
    for test, trace in result.errors[:5]:  # Show first 5
        print(f"  - {test}")

sys.exit(0 if result.wasSuccessful() else 1)
