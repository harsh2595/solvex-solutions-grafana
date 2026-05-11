#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-.}"
status=0

while IFS= read -r json_file; do
  echo "Validating ${json_file}"
  if ! python3 -m json.tool "$json_file" >/dev/null; then
    status=1
  fi
done < <(find "$ROOT_DIR/grafana" -type f -name '*.json' | sort)

exit "$status"
