#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$repo_root/infrastructure/terraform/.build/lambda"
zip_path="$repo_root/infrastructure/terraform/.build/image_processor.zip"
mkdir -p "$build_dir"
python3 -m pip install \
  --only-binary=:all: \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --abi cp312 \
  --target "$build_dir" \
  'Pillow>=10.4,<14'
cp "$repo_root/backend/lambda/image_processor/handler.py" "$build_dir/handler.py"
cp "$repo_root/backend/lambda/image_processor/imaging.py" "$build_dir/imaging.py"
python3 -c 'import os, sys, zipfile; root, dest = sys.argv[1:]; os.makedirs(os.path.dirname(dest), exist_ok=True); z = zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED); [z.write(os.path.join(p, f), os.path.relpath(os.path.join(p, f), root)) for p, _, fs in os.walk(root) for f in fs]; z.close()' "$build_dir" "$zip_path"
printf 'Created %s\n' "$zip_path"
