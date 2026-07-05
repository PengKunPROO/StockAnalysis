#!/bin/bash
set -e
ROOT="$(git rev-parse --show-toplevel)"
echo "=== Stock Agent Test Suite ==="

# Backend tests
echo "[1/4] Backend Tests..."
cd "$ROOT/backend"
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Frontend build
echo "[2/4] Frontend Build..."
cd "$ROOT/frontend"
npx tsc --noEmit
npx vite build --logLevel error

# Integrity checks
echo "[3/4] Integrity Checks..."
cd "$ROOT/frontend/src"
grep -q "kline-container" index.css || { echo "FAIL: kline-container"; exit 1; }
grep -q "right-panel" index.css || { echo "FAIL: right-panel"; exit 1; }
grep -q "info-card" index.css || { echo "FAIL: info-card"; exit 1; }
grep -q "KlineChart" App.tsx || { echo "FAIL: KlineChart import"; exit 1; }
grep -q "DiagnosisPanel" App.tsx || { echo "FAIL: DiagnosisPanel import"; exit 1; }
grep -q "InfoCards" App.tsx || { echo "FAIL: InfoCards import"; exit 1; }
echo "  Integrity checks: OK"

# Port consistency
echo "[4/4] Config Consistency..."
cd "$ROOT"
VITE_PORT=$(grep -oP 'localhost:\K\d+' frontend/vite.config.ts)
START_PORT=$(grep -oP 'port \K\d+' start.bat | head -1)
if [ "$VITE_PORT" != "$START_PORT" ]; then
  echo "FAIL: Port mismatch — vite:${VITE_PORT} vs start.bat:${START_PORT}"
  exit 1
fi
DIAG_PORT=$(grep -oP 'localhost:\K\d+' backend/app/api/v1/diagnosis.py | head -1)
if [ "$DIAG_PORT" != "$VITE_PORT" ]; then
  echo "FAIL: Agent prompt port mismatch — diag:${DIAG_PORT} vs proxy:${VITE_PORT}"
  exit 1
fi
echo "  Port consistency: ALL $VITE_PORT"

echo ""
echo "=== ALL TESTS PASSED ==="
