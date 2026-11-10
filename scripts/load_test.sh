#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 https://your-cloudfront-domain [requests=1000] [parallel=30]" >&2
  exit 2
fi
base_url="${1%/}"
requests="${2:-1000}"
parallel="${3:-30}"
seq "$requests" | xargs -n1 -P "$parallel" -I{} curl --silent --show-error --fail "$base_url/api/listings" -o /dev/null
echo "Sent $requests requests at concurrency $parallel to $base_url/api/listings"
