#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$repo_root/frontend"
if [[ -z "${VITE_COGNITO_REGION:-}" || -z "${VITE_COGNITO_CLIENT_ID:-}" ]]; then
  echo "Set VITE_COGNITO_REGION and VITE_COGNITO_CLIENT_ID from Terraform outputs before building." >&2
  exit 2
fi
cat >"$frontend_dir/.env.production.local" <<EOF
VITE_API_BASE=
VITE_COGNITO_REGION=$VITE_COGNITO_REGION
VITE_COGNITO_CLIENT_ID=$VITE_COGNITO_CLIENT_ID
EOF
cd "$frontend_dir"
npm ci
npm run build
