#!/usr/bin/env bash
# Guards F1a / E1d: "No magic numbers in components" and "no threshold duplicated
# in client code". Fails if any of the PRD-named threshold literals (or the
# TAD-invented cardWidthPx) appear anywhere under frontend/src/features or
# frontend/src/components — the only legitimate home for these numbers is
# frontend/src/config/ (ConfigProvider + the generated/curated DTOs).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PATTERN='(^|[^0-9.])(16|32|50|150|380)([^0-9.]|$)'
SEARCH_DIRS=(frontend/src/features frontend/src/components)

found=0
for dir in "${SEARCH_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    # Exclude *.test.ts(x)/*.spec.ts(x): fixtures mocking a config or health
    # response legitimately contain these numbers as literal test data, not
    # as hard-coded thresholds a real component depends on.
    matches=$(grep -RnE --include='*.ts' --include='*.tsx' "$PATTERN" "$dir" \
        | grep -vE '\.(test|spec)\.tsx?:' \
        | sed -E 's://.*$::; s:/\*.*\*/::; s:#.*$::' \
        | grep -vE '"|`|ROW_HEIGHT_PX|POPUP_WIDTH_PX|POPOVER_WIDTH_PX|D16|B16' || true)
    if [ -n "$matches" ]; then
        echo "$matches"
        found=1
    fi
done

if [ "$found" -ne 0 ]; then
    echo ""
    echo "ERROR: Found a threshold-looking numeric literal (16/32/50/150/380)" >&2
    echo "outside frontend/src/config/. Thresholds must come from useConfig()." >&2
    exit 1
fi

echo "OK: no magic threshold numbers found in features/ or components/."
