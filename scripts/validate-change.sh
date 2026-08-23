#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"

run_stage() {
    local name=$1
    shift
    printf 'VALIDATE: %s\n' "$name"
    "$@"
}

validate_changed_secrets() {
    local scanner=.venv/bin/detect-secrets-hook
    if [[ ! -x $scanner ]]; then
        printf 'Changed-file secret scanner is unavailable: %s\n' "$scanner" >&2
        return 1
    fi
    mapfile -t changed_files < <(
        {
            git diff --name-only --diff-filter=ACM
            git diff --cached --name-only --diff-filter=ACM
            git ls-files --others --exclude-standard
        } \
            | sort -u \
            | grep -Ev '^(\.local/|.*__pycache__/|.*\.pyc$)' \
            || true
    )
    if (( ${#changed_files[@]} > 0 )); then
        "$scanner" --baseline .secrets.baseline "${changed_files[@]}"
    fi
}

declare -a test_directories=()
focused_validation=false
if (( $# > 0 )); then
    focused_validation=true
    for directory in "$@"; do
        if [[ $directory != tests/* || ! -d $directory ]]; then
            printf 'Invalid unittest directory: %s\n' "$directory" >&2
            exit 2
        fi
        test_directories+=("$directory")
    done
else
    mapfile -t test_directories < <(
        find tests -mindepth 1 -maxdepth 1 -type d \
            -exec sh -c 'find "$1" -maxdepth 1 -type f -name "test_*.py" -print -quit | grep -q .' sh {} \; \
            -print \
            | sort
    )
fi

mapfile -t test_directories < <(printf '%s\n' "${test_directories[@]}" | sort -u)

run_stage "experiment isolation" ./scripts/validate-experiment-isolation.sh
run_stage "working-tree whitespace" git diff --check
run_stage "staged whitespace" git diff --cached --check
run_stage "Python compilation" python -m compileall -q src capabilities tests
run_stage "shell syntax" bash -c \
    'find scripts tests -type f -name "*.sh" -print0 | xargs -0r -n1 bash -n'
run_stage "changed-file secret scan" validate_changed_secrets
run_stage "ADR validation" ./scripts/validate_adr.sh
run_stage "supply-chain and workflow validation" python3 scripts/security/validate-supply-chain.py

for directory in "${test_directories[@]}"; do
    run_stage "unittest discovery: $directory" \
        python -m unittest discover -s "$directory" -p 'test_*.py'
done

if [[ $focused_validation == false ]]; then
    mapfile -t bash_tests < <(find tests -type f -name '*-test.sh' -print | sort)
    for test_file in "${bash_tests[@]}"; do
        run_stage "Bash test: $test_file" "$test_file"
    done
fi
