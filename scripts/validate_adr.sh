#!/bin/bash

set -euo pipefail

ADR_DIR="docs/adr"

echo "Validating ADR documents..."

if [ ! -d "$ADR_DIR" ]; then
    echo "ERROR: ADR directory missing"
    exit 1
fi

count=$(find "$ADR_DIR" -name "*.md" | wc -l)

if [ "$count" -eq 0 ]; then
    echo "ERROR: No ADR files found"
    exit 1
fi

echo "Found $count ADR documents"

for file in "$ADR_DIR"/*.md
do
    echo "Checking $file"

    grep -q "# ADR-" "$file" || {
        echo "Missing ADR title: $file"
        exit 1
    }

    grep -q "## Status" "$file" || {
        echo "Missing Status section: $file"
        exit 1
    }

    grep -q "## Context" "$file" || {
        echo "Missing Context section: $file"
        exit 1
    }

    grep -q "# Decision" "$file" || {
        echo "Missing Decision section: $file"
        exit 1
    }

done

echo "ADR validation successful"
