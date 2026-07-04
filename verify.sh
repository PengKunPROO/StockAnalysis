#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Stock Agent Test Suite ==="

# Backend tests
echo "[1/3] Backend Tests..."
cd "$ROOT/backend"
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Frontend build
echo "[2/3] Frontend Build..."
cd "$ROOT/frontend"
npx tsc --noEmit
npx vite build --logLevel error

# Integrity checks
echo "[3/3] Integrity Checks..."
cd "$ROOT/frontend/src"
grep -q "kline-container" index.css || { echo "FAIL: kline-container"; exit 1; }
grep -q "right-panel" index.css || { echo "FAIL: right-panel"; exit 1; }
grep -q "info-card" index.css || { echo "FAIL: info-card"; exit 1; }
grep -q "KlineChart" App.tsx || { echo "FAIL: KlineChart import"; exit 1; }
grep -q "DiagnosisPanel" App.tsx || { echo "FAIL: DiagnosisPanel import"; exit 1; }
grep -q "InfoCards" App.tsx || { echo "FAIL: InfoCards import"; exit 1; }
echo "  Integrity checks: OK"

echo ""
echo "=== ALL TESTS PASSED ==="
