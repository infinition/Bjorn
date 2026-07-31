#!/usr/bin/env bash
#
# Validate Bjorn's clean stop and subsequent restart.

set -Eeuo pipefail

SERVICE_NAME="bjorn.service"
TARGET_DIR="/home/bjorn/Bjorn"
WEB_PORT=8000
EXPECTED_HTTP="auto"
STOP_TIMEOUT=30
PORT_RELEASE_TIMEOUT=90
ORIGINALLY_ACTIVE=0
TEST_FINISHED=0

usage() {
    cat <<'EOF'
Usage:
  sudo ./tests/validate_scan_lifecycle.sh [options]

Options:
  --service UNIT         Systemd service (default: bjorn.service)
  --target PATH          Live Bjorn directory (default: /home/bjorn/Bjorn)
  --port PORT            Expected web port (default: 8000)
  --expect-http CODE     Expected HTTP code: auto, 200, or 401 (default: auto)
  --stop-timeout SEC     Maximum clean stop time (default: 30)
  --port-timeout SEC     Maximum port-release wait (default: 90)
  -h, --help             Show this help

This test performs one real service stop and restart. On failure it attempts
to return a service that was originally active to the active state.
EOF
}

fail() {
    echo "LIFECYCLE_FAIL: $*" >&2
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
        --target)
            require_value "$1" "${2:-}"
            TARGET_DIR="$2"
            shift 2
            ;;
        --port)
            require_value "$1" "${2:-}"
            WEB_PORT="$2"
            shift 2
            ;;
        --expect-http)
            require_value "$1" "${2:-}"
            EXPECTED_HTTP="$2"
            shift 2
            ;;
        --stop-timeout)
            require_value "$1" "${2:-}"
            STOP_TIMEOUT="$2"
            shift 2
            ;;
        --port-timeout)
            require_value "$1" "${2:-}"
            PORT_RELEASE_TIMEOUT="$2"
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

[[ $EUID -eq 0 ]] || fail "run this lifecycle test with sudo"
require_positive_integer "--port" "$WEB_PORT"
require_positive_integer "--stop-timeout" "$STOP_TIMEOUT"
require_positive_integer "--port-timeout" "$PORT_RELEASE_TIMEOUT"
[[ "$EXPECTED_HTTP" == "auto" ||
   "$EXPECTED_HTTP" == "200" ||
   "$EXPECTED_HTTP" == "401" ]] || \
    fail "--expect-http must be auto, 200, or 401"

TARGET_DIR="$(readlink -f -- "$TARGET_DIR")"
[[ -f "$TARGET_DIR/Bjorn.py" ]] || \
    fail "Bjorn.py not found in target: $TARGET_DIR"
systemctl cat "$SERVICE_NAME" >/dev/null || \
    fail "service not found: $SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME" || \
    fail "service is not active: $SERVICE_NAME"
ORIGINALLY_ACTIVE=1

INITIAL_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
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

wait_for_web_port_release() {
    local webapp_file="$TARGET_DIR/webapp.py"
    local second

    if [[ -f "$webapp_file" ]] && \
       grep -Eq 'allow_reuse_address[[:space:]]*=[[:space:]]*True' \
           "$webapp_file"; then
        return 0
    fi

    command -v ss >/dev/null || \
        fail "ss is required to wait for port $WEB_PORT"
    for ((second = 0; second <= PORT_RELEASE_TIMEOUT; second++)); do
        if ! ss -Htan state time-wait "sport = :$WEB_PORT" |
             grep -q . &&
           ! ss -Hltn "sport = :$WEB_PORT" |
             grep -q .; then
            return 0
        fi
        if ((second % 5 == 0)); then
            printf 'Waiting for port %s: %s/%ss\n' \
                "$WEB_PORT" "$second" "$PORT_RELEASE_TIMEOUT"
        fi
        sleep 1
    done
    fail "port $WEB_PORT was not released within $PORT_RELEASE_TIMEOUT seconds"
}

start_and_wait() {
    local second
    local state
    local status

    wait_for_web_port_release
    systemctl reset-failed "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
    for ((second = 0; second < 45; second++)); do
        state="$(systemctl is-active "$SERVICE_NAME" || true)"
        status="$(
            curl --silent --output /dev/null --write-out '%{http_code}' \
                --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
        )"
        if [[ "$state" == "active" && "$status" == "$EXPECTED_HTTP" ]]; then
            return 0
        fi
        sleep 1
    done
    fail "service did not return with HTTP $EXPECTED_HTTP on port $WEB_PORT"
}

recover_service() {
    local exit_code=$?
    local recover_http=""
    local recover_state=""
    local second

    if ((exit_code != 0 && ORIGINALLY_ACTIVE == 1 && TEST_FINISHED == 0)); then
        echo "Attempting to recover $SERVICE_NAME after test failure..." >&2
        set +e
        if ! systemctl is-active --quiet "$SERVICE_NAME"; then
            wait_for_web_port_release
            systemctl reset-failed "$SERVICE_NAME"
            systemctl start "$SERVICE_NAME"
        fi
        for ((second = 0; second < 45; second++)); do
            recover_state="$(systemctl is-active "$SERVICE_NAME" || true)"
            recover_http="$(
                curl --silent --output /dev/null --write-out '%{http_code}' \
                    --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
            )"
            if [[ "$recover_state" == "active" &&
                  "$recover_http" == "$EXPECTED_HTTP" ]]; then
                echo "RECOVERY_OK SERVICE=$recover_state HTTP=$recover_http" >&2
                break
            fi
            sleep 1
        done
        if [[ "$recover_state" != "active" ||
              "$recover_http" != "$EXPECTED_HTTP" ]]; then
            echo "RECOVERY_FAIL SERVICE=$recover_state HTTP=$recover_http" >&2
        fi
    fi
    exit "$exit_code"
}
trap recover_service EXIT

STOP_STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
STOP_STARTED_SECONDS="$SECONDS"
set +e
systemctl stop "$SERVICE_NAME"
STOP_COMMAND_RESULT=$?
set -e
STOP_DURATION="$((SECONDS - STOP_STARTED_SECONDS))"
STOP_STATE="$(systemctl is-active "$SERVICE_NAME" || true)"
STOP_SUBSTATE="$(systemctl show "$SERVICE_NAME" -p SubState --value)"
STOP_RESULT="$(systemctl show "$SERVICE_NAME" -p Result --value)"

if [[ "$STOP_STATE" != "inactive" ]]; then
    echo "Stop diagnostics:" >&2
    printf 'COMMAND_RESULT=%s STATE=%s SUBSTATE=%s RESULT=%s DURATION=%ss\n' \
        "$STOP_COMMAND_RESULT" \
        "$STOP_STATE" \
        "$STOP_SUBSTATE" \
        "$STOP_RESULT" \
        "$STOP_DURATION" >&2
    journalctl -u "$SERVICE_NAME" \
        --since "$STOP_STARTED_AT" \
        --no-pager \
        -o cat |
        tail -80 >&2
    fail "service did not reach inactive state"
fi
((STOP_COMMAND_RESULT == 0)) || \
    fail "systemctl stop returned $STOP_COMMAND_RESULT"
((STOP_DURATION <= STOP_TIMEOUT)) || \
    fail "service stop took ${STOP_DURATION}s, limit is ${STOP_TIMEOUT}s"
if pgrep -f -- "$TARGET_DIR/Bjorn.py" >/dev/null; then
    fail "Bjorn.py process remains after service stop"
fi

STOP_JOURNAL="$(mktemp)"
journalctl -u "$SERVICE_NAME" --since "$STOP_STARTED_AT" --no-pager \
    >"$STOP_JOURNAL"
grep -q 'Main loop finished. Clean exit.' "$STOP_JOURNAL" || {
    rm -f -- "$STOP_JOURNAL"
    fail "clean-exit log entry was not found"
}
SHUTDOWN_ERROR_PATTERN='Fatal Python error|Traceback|Exception in thread|status=[0-9]+/ABRT|Failed with result|Main process exited|timed out'
if grep -qiE "$SHUTDOWN_ERROR_PATTERN" "$STOP_JOURNAL"; then
    echo "Relevant shutdown errors:" >&2
    grep -iE "$SHUTDOWN_ERROR_PATTERN" "$STOP_JOURNAL" >&2 || true
    rm -f -- "$STOP_JOURNAL"
    fail "shutdown errors found in journal"
fi
rm -f -- "$STOP_JOURNAL"

start_and_wait
RESTARTED_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
[[ "$RESTARTED_PID" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid restarted service PID: $RESTARTED_PID"
[[ "$RESTARTED_PID" != "$INITIAL_PID" ]] || \
    fail "service PID did not change across stop/start"

TEST_FINISHED=1
trap - EXIT
printf 'LIFECYCLE_OK STOP_DURATION=%ss OLD_PID=%s NEW_PID=%s HTTP=%s\n' \
    "$STOP_DURATION" "$INITIAL_PID" "$RESTARTED_PID" "$EXPECTED_HTTP"
