#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/web"
if [[ ! -f package-lock.json ]]; then
  echo "No package-lock.json yet: npm install will generate one; commit it for reproducible installs." >&2
  npm install --no-audit --no-fund
else
  npm ci --no-audit --no-fund
fi
npm run typecheck
npm run lint
npm run build
