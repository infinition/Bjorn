#!/usr/bin/env bash
#
# Run Bjorn scan-worker checks at unit and/or live-runtime level.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
WEB_PORT=8000
DURATION=30
SCAN_TIMEOUT=90
THREAD_LIMIT=64
EXPECTED_HTTP="auto"
RUN_LEVEL="all"

usage() {
    cat <<'EOF'
Usage:
  ./tests/run_scan_worker_validation.sh --unit
  sudo ./tests/run_scan_worker_validation.sh --runtime [options]
  sudo ./tests/run_scan_worker_validation.sh --all [options]

Levels:
  --unit              Syntax, compile, and Python unit tests only
  --runtime           Installed-file, stability, and lifecycle tests only
  --all               Unit plus runtime tests (default)

Runtime options:
  --target PATH       Live Bjorn directory (default: /home/bjorn/Bjorn)
  --service UNIT      Systemd service (default: bjorn.service)
  --port PORT         Expected web port (default: 8000)
  --duration SEC      Stability observation time (default: 30)
  --scan-timeout SEC  Maximum time from test start for one scan (default: 90)
  --thread-limit N    Maximum allowed process threads (default: 64)
  --expect-http CODE  auto, 200, or 401 (default: auto)
  -h, --help          Show this help
EOF
}

fail() {
    echo "VALIDATION_FAIL: $*" >&2
    exit 1
}

require_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "$value" ]] || fail "$option requires a value"
}

while (($#)); do
    case "$1" in
        --unit|--runtime|--all)
            RUN_LEVEL="${1#--}"
            shift
            ;;
        --target)
            require_value "$1" "${2:-}"
            TARGET_DIR="$2"
            shift 2
            ;;
        --service)
            require_value "$1" "${2:-}"
            SERVICE_NAME="$2"
            shift 2
            ;;
        --port)
            require_value "$1" "${2:-}"
            WEB_PORT="$2"
            shift 2
            ;;
        --duration)
            require_value "$1" "${2:-}"
            DURATION="$2"
            shift 2
            ;;
        --scan-timeout)
            require_value "$1" "${2:-}"
            SCAN_TIMEOUT="$2"
            shift 2
            ;;
        --thread-limit)
            require_value "$1" "${2:-}"
            THREAD_LIMIT="$2"
            shift 2
            ;;
        --expect-http)
            require_value "$1" "${2:-}"
            EXPECTED_HTTP="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
done

run_unit_tests() {
    echo "== Unit level =="
    bash -n "$PROJECT_DIR/install_stability_web_auth.sh"
    bash -n "$SCRIPT_DIR/validate_scan_runtime.sh"
    bash -n "$SCRIPT_DIR/validate_scan_lifecycle.sh"
    bash -n "$SCRIPT_DIR/run_scan_worker_validation.sh"
    python3 -m py_compile \
        "$PROJECT_DIR/actions/scanning.py" \
        "$PROJECT_DIR/Bjorn.py" \
        "$PROJECT_DIR/display.py" \
        "$PROJECT_DIR/epd_helper.py" \
        "$PROJECT_DIR/webapp.py"
    (
        cd "$PROJECT_DIR"
        python3 -m unittest discover -s tests -p 'test_*.py' -v
    )
    echo "UNIT_LEVEL_OK"
}

verify_webapp_lifecycle_contract() {
    local webapp="$TARGET_DIR/webapp.py"

    [[ -f "$webapp" ]] || \
        fail "live webapp.py is missing"

    grep -Eq \
        'allow_reuse_address[[:space:]]*=[[:space:]]*True' \
        "$webapp" || \
        fail "live webapp.py is missing reusable-port support"
    grep -Eq \
        'httpd\.timeout[[:space:]]*=[[:space:]]*0\.5' \
        "$webapp" || \
        fail "live webapp.py is missing the bounded request timeout"
    grep -Eq \
        'super\(\)\.__init__\(name="BjornWeb"\)' \
        "$webapp" || \
        fail "live webapp.py is missing the named non-daemon web thread"
    grep -Fq \
        'Unexpected web server thread error ' \
        "$webapp" || \
        fail "live webapp.py is missing controlled thread-error handling"

    if cmp -s "$PROJECT_DIR/webapp.py" "$webapp"; then
        echo "WEBAPP_LIFECYCLE_EXACT_MATCH"
    else
        echo "WEBAPP_LIFECYCLE_COMPATIBLE_LAYER"
    fi
}

run_runtime_tests() {
    echo "== Runtime level =="
    [[ $EUID -eq 0 ]] || \
        fail "run runtime/all validation with sudo"

    TARGET_DIR="$(readlink -f -- "$TARGET_DIR")"
    cmp -s "$PROJECT_DIR/Bjorn.py" "$TARGET_DIR/Bjorn.py" || \
        fail "live Bjorn.py does not match the tested contribution"
    cmp -s \
        "$PROJECT_DIR/actions/scanning.py" \
        "$TARGET_DIR/actions/scanning.py" || \
        fail "live actions/scanning.py does not match the tested contribution"
    cmp -s "$PROJECT_DIR/display.py" "$TARGET_DIR/display.py" || \
        fail "live display.py does not match the tested contribution"
    cmp -s "$PROJECT_DIR/epd_helper.py" "$TARGET_DIR/epd_helper.py" || \
        fail "live epd_helper.py does not match the tested contribution"
    verify_webapp_lifecycle_contract
    echo "INSTALLED_FILES_MATCH"

    "$SCRIPT_DIR/validate_scan_runtime.sh" \
        --service "$SERVICE_NAME" \
        --port "$WEB_PORT" \
        --duration "$DURATION" \
        --scan-timeout "$SCAN_TIMEOUT" \
        --thread-limit "$THREAD_LIMIT" \
        --expect-http "$EXPECTED_HTTP"

    "$SCRIPT_DIR/validate_scan_lifecycle.sh" \
        --service "$SERVICE_NAME" \
        --target "$TARGET_DIR" \
        --port "$WEB_PORT" \
        --expect-http "$EXPECTED_HTTP"

    echo "RUNTIME_LEVEL_OK"
}

case "$RUN_LEVEL" in
    unit)
        run_unit_tests
        ;;
    runtime)
        run_runtime_tests
        ;;
    all)
        run_unit_tests
        run_runtime_tests
        ;;
    *)
        fail "unsupported validation level: $RUN_LEVEL"
        ;;
esac

echo "SCAN_WORKER_VALIDATION_OK level=$RUN_LEVEL"
