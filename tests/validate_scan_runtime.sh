#!/usr/bin/env bash
#
# Validate a running Bjorn scanner without restarting the service.

set -Eeuo pipefail

SERVICE_NAME="bjorn.service"
WEB_PORT=8000
DURATION=30
SCAN_TIMEOUT=90
THREAD_LIMIT=64
EXPECTED_HTTP="auto"

usage() {
    cat <<'EOF'
Usage:
  sudo ./tests/validate_scan_runtime.sh [options]

Options:
  --service UNIT       Systemd service (default: bjorn.service)
  --port PORT          Expected web port (default: 8000)
  --duration SECONDS   Observation time (default: 30)
  --scan-timeout SEC   Maximum time from test start for one scan (default: 90)
  --thread-limit N     Fail above this process thread count (default: 64)
  --expect-http CODE   Expected HTTP code: auto, 200, or 401 (default: auto)
  -h, --help           Show this help

The test keeps the service running and verifies a stable PID, HTTP response,
bounded process thread count, at least one completed scan for the current
process, and absence of scanner/thread-pool errors in its journal.
EOF
}

fail() {
    echo "RUNTIME_FAIL: $*" >&2
    exit 1
}

require_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "$value" ]] || fail "$option requires a value"
}

require_positive_integer() {
    local option="$1"
    local value="$2"
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || \
        fail "$option requires a positive integer"
}

while (($#)); do
    case "$1" in
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

[[ $EUID -eq 0 ]] || fail "run this runtime test with sudo"
require_positive_integer "--port" "$WEB_PORT"
require_positive_integer "--duration" "$DURATION"
require_positive_integer "--scan-timeout" "$SCAN_TIMEOUT"
require_positive_integer "--thread-limit" "$THREAD_LIMIT"
((SCAN_TIMEOUT >= DURATION)) || \
    fail "--scan-timeout must be greater than or equal to --duration"
[[ "$EXPECTED_HTTP" == "auto" ||
   "$EXPECTED_HTTP" == "200" ||
   "$EXPECTED_HTTP" == "401" ]] || \
    fail "--expect-http must be auto, 200, or 401"

systemctl cat "$SERVICE_NAME" >/dev/null || \
    fail "service not found: $SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME" || \
    fail "service is not active: $SERVICE_NAME"

SERVICE_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
[[ "$SERVICE_PID" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid service PID: $SERVICE_PID"
kill -0 "$SERVICE_PID" 2>/dev/null || \
    fail "service PID is not running: $SERVICE_PID"

INITIAL_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
if [[ "$EXPECTED_HTTP" == "auto" ]]; then
    [[ "$INITIAL_HTTP" == "200" || "$INITIAL_HTTP" == "401" ]] || \
        fail "initial web response is HTTP $INITIAL_HTTP, expected 200 or 401"
    EXPECTED_HTTP="$INITIAL_HTTP"
elif [[ "$INITIAL_HTTP" != "$EXPECTED_HTTP" ]]; then
    fail "initial web response is HTTP $INITIAL_HTTP, expected $EXPECTED_HTTP"
fi

MAX_THREADS=0
check_runtime_sample() {
    CURRENT_STATE="$(systemctl is-active "$SERVICE_NAME" || true)"
    CURRENT_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
    CURRENT_HTTP="$(
        curl --silent --output /dev/null --write-out '%{http_code}' \
            --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
    )"
    CURRENT_THREADS="$(
        ps -o nlwp= -p "$SERVICE_PID" 2>/dev/null |
            tr -d '[:space:]'
    )"

    [[ "$CURRENT_STATE" == "active" ]] || \
        fail "service state changed to: $CURRENT_STATE"
    [[ "$CURRENT_PID" == "$SERVICE_PID" ]] || \
        fail "service PID changed from $SERVICE_PID to $CURRENT_PID"
    [[ "$CURRENT_HTTP" == "$EXPECTED_HTTP" ]] || \
        fail "web response changed from HTTP $EXPECTED_HTTP to $CURRENT_HTTP"
    [[ "$CURRENT_THREADS" =~ ^[1-9][0-9]*$ ]] || \
        fail "could not read thread count for PID $SERVICE_PID"
    ((CURRENT_THREADS <= THREAD_LIMIT)) || \
        fail "thread limit exceeded: $CURRENT_THREADS > $THREAD_LIMIT"

    if ((CURRENT_THREADS > MAX_THREADS)); then
        MAX_THREADS="$CURRENT_THREADS"
    fi
}

for ((second = 1; second <= DURATION; second++)); do
    check_runtime_sample
    printf '\rRuntime: %02d/%ss | Threads: %s | Maximum: %s' \
        "$second" "$DURATION" "$CURRENT_THREADS" "$MAX_THREADS"
    sleep 1
done
echo

completed_scan_count() {
    journalctl "_PID=$SERVICE_PID" --no-pager |
        grep -c 'Scan results cleaned up' || true
}

COMPLETED_SCANS="$(completed_scan_count)"
if ! [[ "$COMPLETED_SCANS" =~ ^[1-9][0-9]*$ ]]; then
    for ((second = DURATION + 1; second <= SCAN_TIMEOUT; second++)); do
        check_runtime_sample
        COMPLETED_SCANS="$(completed_scan_count)"
        printf '\rWaiting for scan completion: %02d/%ss | Threads: %s | Maximum: %s' \
            "$second" "$SCAN_TIMEOUT" "$CURRENT_THREADS" "$MAX_THREADS"
        if [[ "$COMPLETED_SCANS" =~ ^[1-9][0-9]*$ ]]; then
            break
        fi
        sleep 1
    done
    echo
fi

JOURNAL_FILE="$(mktemp)"
trap 'rm -f -- "$JOURNAL_FILE"' EXIT
journalctl "_PID=$SERVICE_PID" --no-pager >"$JOURNAL_FILE"

ERROR_PATTERN='cannot schedule|can.t start new thread|pthread_create|Error in scan|Fatal Python error|Traceback|Exception in thread|status=[0-9]+/ABRT'
if grep -qiE "$ERROR_PATTERN" "$JOURNAL_FILE"; then
    echo "Relevant journal errors:" >&2
    grep -iE "$ERROR_PATTERN" "$JOURNAL_FILE" >&2 || true
    fail "scanner or thread-pool errors found for PID $SERVICE_PID"
fi

COMPLETED_SCANS="$(grep -c 'Scan results cleaned up' "$JOURNAL_FILE" || true)"
RESULT_WRITES="$(
    grep -c 'Results saved to' "$JOURNAL_FILE" || true
)"
[[ "$COMPLETED_SCANS" =~ ^[1-9][0-9]*$ ]] || \
    fail "no completed scan found for PID $SERVICE_PID"
[[ "$RESULT_WRITES" =~ ^[1-9][0-9]*$ ]] || \
    fail "no saved scan result found for PID $SERVICE_PID"

printf 'RUNTIME_OK PID=%s HTTP=%s MAX_THREADS=%s COMPLETED_SCANS=%s\n' \
    "$SERVICE_PID" "$EXPECTED_HTTP" "$MAX_THREADS" "$COMPLETED_SCANS"
