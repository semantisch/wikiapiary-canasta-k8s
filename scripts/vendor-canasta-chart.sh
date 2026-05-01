#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "usage: $0 /path/to/Canasta-CLI" >&2
  exit 1
fi

SOURCE_ROOT=$1
SOURCE_CHART="$SOURCE_ROOT/roles/orchestrator/files/helm/canasta"
TARGET_CHART="$(cd "$(dirname "$0")/.." && pwd)/charts/canasta"

if [ ! -d "$SOURCE_CHART" ]; then
  echo "missing chart at $SOURCE_CHART" >&2
  exit 1
fi

rm -rf "$TARGET_CHART"
mkdir -p "$(dirname "$TARGET_CHART")"
cp -R "$SOURCE_CHART" "$TARGET_CHART"

echo "vendored Canasta chart into $TARGET_CHART"
