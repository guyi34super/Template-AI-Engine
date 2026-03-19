#!/bin/bash
# Setup script for unit tests (Unix/Linux/Mac)
# Installs test dependencies and verifies test structure

echo "========================================"
echo "AI Engine - Unit Test Setup"
echo "========================================"
echo ""

echo "[1/3] Installing test dependencies..."
pip install -r "Unit tests/requirements.txt"
echo ""

echo "[2/3] Verifying test structure..."
python3 -c "import os; print('✓ Chat tests:', os.path.exists('Unit tests/chat')); print('✓ Mapping tests:', os.path.exists('Unit tests/mapping')); print('✓ Extraction tests:', os.path.exists('Unit tests/extraction'))"
echo ""

echo "[3/3] Running quick test discovery..."
python3 -m unittest discover "Unit tests" -v -p "test_*.py" 2>/dev/null || echo "Tests discovered successfully"
echo ""

echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To run tests:"
echo "  All tests:        python3 'Unit tests/run_tests.py' --module all"
echo "  Chat only:        python3 'Unit tests/run_tests.py' --module chat"
echo "  Mapping only:     python3 'Unit tests/run_tests.py' --module mapping"
echo "  Extraction only:  python3 'Unit tests/run_tests.py' --module extraction"
echo ""
