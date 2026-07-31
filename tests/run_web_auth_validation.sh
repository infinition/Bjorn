#!/usr/bin/env bash
#
# Run Bjorn web-auth checks at unit and/or live-runtime level.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
COMMAND_PATH="/usr/local/sbin/http_auth"
WEB_PORT=8000
RUN_LEVEL="all"

usage() {
    cat <<'EOF'
Usage:
  ./tests/run_web_auth_validation.sh --unit
  sudo ./tests/run_web_auth_validation.sh --runtime [options]
  sudo ./tests/run_web_auth_validation.sh --all [options]

Levels:
  --unit              Syntax, compile, and Python tests only
  --runtime           Installed-file and live HTTP/command tests only
  --all               Unit plus runtime tests (default)

Runtime options:
  --target PATH       Live Bjorn directory (default: /home/bjorn/Bjorn)
  --service UNIT      Systemd service (default: bjorn.service)
  --command PATH      Management command (default: /usr/local/sbin/http_auth)
  --port PORT         Web port (default: 8000)
  -h, --help          Show this help
EOF
}

fail() {
    echo "WEB_AUTH_VALIDATION_FAIL: $*" >&2
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
        --command)
            require_value "$1" "${2:-}"
            COMMAND_PATH="$2"
            shift 2
            ;;
        --port)
            require_value "$1" "${2:-}"
            WEB_PORT="$2"
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
    bash -n "$SCRIPT_DIR/validate_web_auth_runtime.sh"
    bash -n "$SCRIPT_DIR/run_web_auth_validation.sh"
    python3 -m py_compile \
        "$PROJECT_DIR/web_auth.py" \
        "$PROJECT_DIR/configure_web_auth.py" \
        "$PROJECT_DIR/webapp.py" \
        "$PROJECT_DIR/shared.py"
    (
        cd "$PROJECT_DIR"
        python3 -m unittest discover -s tests -p 'test_*.py' -v
    )
    echo "UNIT_LEVEL_OK"
}

run_runtime_tests() {
    local resolved_command

    echo "== Runtime level =="
    [[ $EUID -eq 0 ]] || \
        fail "run runtime/all validation with sudo"
    TARGET_DIR="$(readlink -f -- "$TARGET_DIR")"

    for relative_path in \
        web_auth.py \
        configure_web_auth.py \
        webapp.py \
        shared.py; do
        cmp -s \
            "$PROJECT_DIR/$relative_path" \
            "$TARGET_DIR/$relative_path" || \
            fail "live $relative_path does not match the tested contribution"
    done

    [[ -e "$COMMAND_PATH" ]] || \
        fail "management command not found: $COMMAND_PATH"
    resolved_command="$(readlink -f -- "$COMMAND_PATH")"
    [[ "$resolved_command" == "$TARGET_DIR/configure_web_auth.py" ]] || \
        fail "management command points to unexpected file: $resolved_command"
    echo "INSTALLED_FILES_MATCH"

    "$SCRIPT_DIR/validate_web_auth_runtime.sh" \
        --target "$TARGET_DIR" \
        --service "$SERVICE_NAME" \
        --command "$COMMAND_PATH" \
        --port "$WEB_PORT"

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

echo "WEB_AUTH_VALIDATION_OK level=$RUN_LEVEL"
