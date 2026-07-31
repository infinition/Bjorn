#!/usr/bin/env bash
#
# Run the complete Bjorn stability and optional web-auth contribution checks.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
COMMAND_PATH="/usr/local/sbin/http_auth"
WEB_PORT=8000
DURATION=30
SCAN_TIMEOUT=90
THREAD_LIMIT=64
RUN_LEVEL="all"
VERBOSE=false
PYTHON_BIN="${PYTHON_BIN:-python3}"
UNIT_SECTION_LABEL="[1/3]"
SCAN_SECTION_LABEL="[2/3]"
AUTH_SECTION_LABEL="[3/3]"
ACTIVE_CHILD_PID=""
LAST_RUN_LOG=""
LAST_RUN_SECONDS=0
TEMP_LOGS=()

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    COLOR_ENABLED=true
    RESET=$'\033[0m'
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    RED=$'\033[31m'
    GREEN=$'\033[32m'
    YELLOW=$'\033[33m'
    CYAN=$'\033[36m'
else
    COLOR_ENABLED=false
    RESET=""
    BOLD=""
    DIM=""
    RED=""
    GREEN=""
    YELLOW=""
    CYAN=""
fi

usage() {
    cat <<'EOF'
Usage:
  ./tests/run_stability_web_auth_validation.sh --unit
  sudo ./tests/run_stability_web_auth_validation.sh --runtime [options]
  sudo ./tests/run_stability_web_auth_validation.sh --all [options]

Levels:
  --unit              Syntax, compile, and all Python tests
  --runtime           Scanner/lifecycle followed by live web-auth validation
  --all               Unit plus runtime validation (default)

Runtime options:
  --target PATH       Live Bjorn directory (default: /home/bjorn/Bjorn)
  --service UNIT      Systemd service (default: bjorn.service)
  --command PATH      Web-auth command (default: /usr/local/sbin/http_auth)
  --port PORT         Web port (default: 8000)
  --duration SEC      Scanner observation time (default: 30)
  --scan-timeout SEC  Maximum time for one scan (default: 90)
  --thread-limit N    Maximum process threads (default: 64)
  --verbose           Show complete output from every underlying test
  -h, --help          Show this help

Colors are enabled automatically on an interactive terminal. Set NO_COLOR=1
to disable them. Set PYTHON_BIN to override the Python executable used by the
unit level (default: python3).
EOF
}

fail() {
    printf '%s[FAIL]%s %s\n' "$RED$BOLD" "$RESET" "$*" >&2
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
        --verbose)
            VERBOSE=true
            shift
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

case "$RUN_LEVEL" in
    unit)
        UNIT_SECTION_LABEL="[1/1]"
        ;;
    runtime)
        SCAN_SECTION_LABEL="[1/2]"
        AUTH_SECTION_LABEL="[2/2]"
        ;;
esac

cleanup() {
    local log_file
    if [[ -n "$ACTIVE_CHILD_PID" ]] && \
       kill -0 "$ACTIVE_CHILD_PID" 2>/dev/null; then
        kill -TERM "$ACTIVE_CHILD_PID" 2>/dev/null || true
        wait "$ACTIVE_CHILD_PID" 2>/dev/null || true
    fi
    for log_file in "${TEMP_LOGS[@]}"; do
        rm -f -- "$log_file"
    done
}

handle_interrupt() {
    printf '\n%s[STOP]%s Validation interrupted; cleaning up...\n' \
        "$YELLOW$BOLD" "$RESET" >&2
    exit 130
}

trap cleanup EXIT
trap handle_interrupt INT TERM

banner() {
    printf '\n%s%sBjorn stability and web-auth validation%s\n' \
        "$BOLD" "$CYAN" "$RESET"
    printf '%sTarget:%s  %s\n' "$DIM" "$RESET" "$TARGET_DIR"
    printf '%sMode:%s    %s\n\n' "$DIM" "$RESET" "$RUN_LEVEL"
}

section() {
    printf '%s%s%s%s\n' "$BOLD" "$CYAN" "$*" "$RESET"
}

success() {
    printf '  %s[OK]%s %s\n' "$GREEN$BOLD" "$RESET" "$*"
}

detail() {
    printf '       %s%s%s\n' "$DIM" "$*" "$RESET"
}

log_value() {
    local log_file="$1"
    local marker="$2"
    local key="$3"
    grep -E "^${marker}( |$)" "$log_file" |
        tail -1 |
        sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p"
}

run_captured() {
    local label="$1"
    shift
    local log_file
    local started
    local elapsed
    local status

    log_file="$(mktemp)"
    TEMP_LOGS+=("$log_file")
    started=$SECONDS

    if [[ "$VERBOSE" == true ]]; then
        printf '  %s...%s %s\n' "$CYAN" "$RESET" "$label"
        set +e
        "$@" 2>&1 | tee "$log_file"
        status=${PIPESTATUS[0]}
        set -e
    else
        "$@" >"$log_file" 2>&1 &
        ACTIVE_CHILD_PID=$!
        if [[ "$COLOR_ENABLED" == true ]]; then
            while kill -0 "$ACTIVE_CHILD_PID" 2>/dev/null; do
                elapsed=$((SECONDS - started))
                printf '\r\033[2K  %s[...]%s %s (%ss)' \
                    "$CYAN$BOLD" "$RESET" "$label" "$elapsed"
                sleep 1
            done
            printf '\r\033[2K'
        else
            printf '  [...] %s\n' "$label"
        fi
        set +e
        wait "$ACTIVE_CHILD_PID"
        status=$?
        set -e
        ACTIVE_CHILD_PID=""
    fi

    LAST_RUN_SECONDS=$((SECONDS - started))
    LAST_RUN_LOG="$log_file"
    if ((status != 0)); then
        printf '  %s[FAIL]%s %s\n' "$RED$BOLD" "$RESET" "$label" >&2
        printf '\n%s--- complete diagnostic output ---%s\n' \
            "$YELLOW" "$RESET" >&2
        cat "$log_file" >&2
        printf '%s--- end diagnostic output ---%s\n\n' \
            "$YELLOW" "$RESET" >&2
        return "$status"
    fi
    return 0
}

run_static_checks() {
    "$PYTHON_BIN" -c 'import pandas'

    bash -n "$PROJECT_DIR/install_bjorn.sh"
    bash -n "$PROJECT_DIR/install_stability_web_auth.sh"
    bash -n "$SCRIPT_DIR/run_fresh_installer_integration.sh"
    bash -n "$SCRIPT_DIR/run_stability_web_auth_validation.sh"
    bash -n "$SCRIPT_DIR/run_scan_worker_validation.sh"
    bash -n "$SCRIPT_DIR/run_web_auth_validation.sh"
    bash -n "$SCRIPT_DIR/run_reboot_persistence_validation.sh"
    bash -n "$SCRIPT_DIR/validate_scan_runtime.sh"
    bash -n "$SCRIPT_DIR/validate_scan_lifecycle.sh"
    bash -n "$SCRIPT_DIR/validate_web_auth_runtime.sh"

    "$PYTHON_BIN" -m py_compile \
        "$PROJECT_DIR/actions/scanning.py" \
        "$PROJECT_DIR/Bjorn.py" \
        "$PROJECT_DIR/display.py" \
        "$PROJECT_DIR/epd_helper.py" \
        "$PROJECT_DIR/webapp.py" \
        "$PROJECT_DIR/shared.py" \
        "$PROJECT_DIR/web_auth.py" \
        "$PROJECT_DIR/configure_web_auth.py"
}

run_python_tests() {
    cd "$PROJECT_DIR"
    "$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py' -v
}

run_unit_tests() {
    local test_summary

    section "$UNIT_SECTION_LABEL Source and automated tests"
    run_captured "Checking shell and Python syntax" run_static_checks ||
        fail "static checks failed"
    success "Shell syntax and Python compilation"

    run_captured "Running unit and integration tests" run_python_tests ||
        fail "unit or integration tests failed"
    test_summary="$(
        grep -E '^Ran [0-9]+ tests? in [0-9.]+s$' "$LAST_RUN_LOG" |
            tail -1 || true
    )"
    success "${test_summary:-All unit and integration tests passed}"
    detail "Lifecycle, scanner, display/GPIO, credentials, and every web route"

    run_captured "Testing the isolated fresh-installer choices" \
        "$SCRIPT_DIR/run_fresh_installer_integration.sh" ||
        fail "fresh-installer integration test failed"
    success "Fresh-installer decline, install, credentials, and management flow"
}

run_runtime_tests() {
    local scan_pid
    local scan_http
    local max_threads
    local completed_scans
    local stop_duration
    local new_pid
    local challenge_requests
    local post_elapsed
    local invalid_warnings

    [[ $EUID -eq 0 ]] || \
        fail "run runtime/all validation with sudo"

    section "$SCAN_SECTION_LABEL Live scanner and service lifecycle"
    run_captured "Observing a complete scan and service restart" \
        "$SCRIPT_DIR/run_scan_worker_validation.sh" \
        --runtime \
        --target "$TARGET_DIR" \
        --service "$SERVICE_NAME" \
        --port "$WEB_PORT" \
        --duration "$DURATION" \
        --scan-timeout "$SCAN_TIMEOUT" \
        --thread-limit "$THREAD_LIMIT" \
        --expect-http 401 ||
        fail "live scanner or service lifecycle validation failed"

    scan_pid="$(log_value "$LAST_RUN_LOG" RUNTIME_OK PID)"
    scan_http="$(log_value "$LAST_RUN_LOG" RUNTIME_OK HTTP)"
    max_threads="$(log_value "$LAST_RUN_LOG" RUNTIME_OK MAX_THREADS)"
    completed_scans="$(
        log_value "$LAST_RUN_LOG" RUNTIME_OK COMPLETED_SCANS
    )"
    stop_duration="$(
        log_value "$LAST_RUN_LOG" LIFECYCLE_OK STOP_DURATION
    )"
    new_pid="$(log_value "$LAST_RUN_LOG" LIFECYCLE_OK NEW_PID)"
    success "Scanner completed without worker or executor errors"
    local scan_label="scans"
    [[ "${completed_scans:-0}" == "1" ]] && scan_label="scan"
    detail "PID ${scan_pid:-?}, HTTP ${scan_http:-?}, peak ${max_threads:-?} threads, ${completed_scans:-?} completed $scan_label"
    success "Service stopped cleanly and returned on port $WEB_PORT"
    detail "Stop ${stop_duration:-?}, restarted as PID ${new_pid:-?}"

    section "$AUTH_SECTION_LABEL Live web authentication"
    run_captured "Checking commands, routes, and malformed requests" \
        "$SCRIPT_DIR/run_web_auth_validation.sh" \
        --runtime \
        --target "$TARGET_DIR" \
        --service "$SERVICE_NAME" \
        --command "$COMMAND_PATH" \
        --port "$WEB_PORT" ||
        fail "live web-authentication validation failed"

    challenge_requests="$(
        log_value "$LAST_RUN_LOG" HEADERLESS_CHALLENGE_STRESS_OK requests
    )"
    post_elapsed="$(
        log_value "$LAST_RUN_LOG" INCOMPLETE_POST_OK elapsed
    )"
    invalid_warnings="$(
        log_value "$LAST_RUN_LOG" JOURNAL_AUDIT_OK invalid_warnings
    )"
    success "Management commands and every HTTP route are protected"
    success "${challenge_requests:-30} browser challenges completed"
    detail "Incomplete POST rejected in ${post_elapsed:-?}; audit warnings observed: ${invalid_warnings:-?}"
    success "Original credential state restored"
}

banner
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

printf '\n%s%s[PASS] All requested validation levels completed successfully.%s\n' \
    "$GREEN" "$BOLD" "$RESET"
printf '%sMachine marker:%s STABILITY_WEB_AUTH_VALIDATION_OK level=%s\n\n' \
    "$DIM" "$RESET" "$RUN_LEVEL"
