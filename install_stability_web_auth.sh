#!/usr/bin/env bash
#
# Atomically install Bjorn's stability, lifecycle, scanner-worker, and optional
# web-authentication improvements into an existing installation. The script
# creates one rollback snapshot for the complete feature set and restores it
# automatically if validation, installation, or startup fails.

set -Eeuo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
COMMAND_PATH="/usr/local/sbin/http_auth"
CREDENTIAL_SOURCE=""
USERNAME=""
ROLLBACK_ROOT="/home/bjorn"
ROLLBACK_DIR=""
RESTORE_SOURCE=""
INSTALL_STARTED=0
HTTP_STATUS=""
WEB_PORT=8000
PORT_RELEASE_TIMEOUT=90

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    RED=$'\033[0;31m'
    GREEN=$'\033[0;32m'
    YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'
    CYAN=$'\033[0;36m'
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    NC=$'\033[0m'
else
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    CYAN=""
    BOLD=""
    DIM=""
    NC=""
fi

banner() {
    local operation="$1"
    printf '\n%b%s%b\n' "$BOLD$CYAN" \
        "Bjorn stability and web-auth installer" "$NC"
    printf '%b%-12s%b %s\n' "$DIM" "Operation:" "$NC" "$operation"
    printf '%b%-12s%b %s\n' "$DIM" "Target:" "$NC" "$TARGET_DIR"
    printf '%b%-12s%b %s\n\n' "$DIM" "Service:" "$NC" "$SERVICE_NAME"
}

step() {
    local number="$1"
    local total="$2"
    shift 2
    printf '%bStep %s of %s:%b %s\n' \
        "$BOLD$BLUE" "$number" "$total" "$NC" "$*"
}

info() {
    printf '%b[INFO]%b %s\n' "$BLUE" "$NC" "$*"
}

success() {
    printf '%b[OK]%b %s\n' "$GREEN" "$NC" "$*"
}

warning() {
    printf '%b[WARNING]%b %s\n' "$YELLOW" "$NC" "$*" >&2
}

error() {
    printf '%b[ERROR]%b %s\n' "$RED" "$NC" "$*" >&2
}

summary_row() {
    local label="$1"
    shift
    printf '  %b%-20s%b %s\n' "$BOLD" "$label" "$NC" "$*"
}

complete() {
    printf '\n%b[PASS]%b %s\n' "$BOLD$GREEN" "$NC" "$*"
}

usage() {
    cat <<'EOF'
Usage:
  sudo ./install_stability_web_auth.sh [options]

Options:
  --target PATH          Existing Bjorn installation (default: /home/bjorn/Bjorn)
  --service UNIT         Systemd service name (default: bjorn.service)
  --command-path PATH    Management command (default: /usr/local/sbin/http_auth)
  --credentials FILE     Reuse an existing web_auth.json credential file
  --username USER        Prompt for a new password and enable this username
  --rollback-root PATH   Directory for rollback snapshots (default: /home/bjorn)
  --restore SNAPSHOT     Restore a snapshot created by this installer
  -h, --help             Show this help

Use either --credentials or --username, not both. Without either option, all
stability files are installed but authentication remains unconfigured.
Use --restore by itself to return to a previous installer snapshot. A recovery
snapshot of the current state is created before the restore begins.
When restoring Bjorn's original non-reusable web socket, the installer waits
for port 8000 to leave TIME_WAIT before restarting the service.
Colors are enabled automatically on a terminal. Set NO_COLOR=1 to disable them.
EOF
}

fail() {
    error "$*"
    return 1
}

require_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "$value" ]] || fail "$option requires a value"
}

while (($#)); do
    case "$1" in
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
        --command-path)
            require_value "$1" "${2:-}"
            COMMAND_PATH="$2"
            shift 2
            ;;
        --credentials)
            require_value "$1" "${2:-}"
            CREDENTIAL_SOURCE="$2"
            shift 2
            ;;
        --username)
            require_value "$1" "${2:-}"
            USERNAME="$2"
            shift 2
            ;;
        --rollback-root)
            require_value "$1" "${2:-}"
            ROLLBACK_ROOT="$2"
            shift 2
            ;;
        --restore)
            require_value "$1" "${2:-}"
            RESTORE_SOURCE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

[[ $EUID -eq 0 ]] || fail "Run this installer with sudo."
[[ -z "$CREDENTIAL_SOURCE" || -z "$USERNAME" ]] || \
    fail "Use either --credentials or --username, not both."
[[ -z "$RESTORE_SOURCE" || \
   ( -z "$CREDENTIAL_SOURCE" && -z "$USERNAME" ) ]] || \
    fail "Do not combine --restore with --credentials or --username."

SOURCE_DIR="$(readlink -f -- "$SOURCE_DIR")"
TARGET_DIR="$(readlink -f -- "$TARGET_DIR")"
ROLLBACK_ROOT="$(readlink -f -- "$ROLLBACK_ROOT")"
COMMAND_PATH="$(realpath --canonicalize-missing --no-symlinks -- "$COMMAND_PATH")"
if [[ -n "$RESTORE_SOURCE" ]]; then
    [[ -d "$RESTORE_SOURCE" ]] || \
        fail "Restore snapshot not found: $RESTORE_SOURCE"
    RESTORE_SOURCE="$(readlink -f -- "$RESTORE_SOURCE")"
fi

[[ -d "$TARGET_DIR" ]] || fail "Target directory not found: $TARGET_DIR"
[[ -f "$TARGET_DIR/Bjorn.py" ]] || fail "Bjorn.py not found in: $TARGET_DIR"
systemctl cat "$SERVICE_NAME" >/dev/null || fail "Service not found: $SERVICE_NAME"

if [[ -n "$RESTORE_SOURCE" ]]; then
    OPERATION_MODE="Restore"
else
    OPERATION_MODE="Installation"
fi
banner "$OPERATION_MODE"
step 1 5 "Validate inputs and create a recovery snapshot"

if [[ -z "$RESTORE_SOURCE" ]]; then
    REQUIRED_SOURCE_FILES=(
        actions/scanning.py
        Bjorn.py
        display.py
        epd_helper.py
        web_auth.py
        configure_web_auth.py
        webapp.py
        shared.py
    )
    for relative_path in "${REQUIRED_SOURCE_FILES[@]}"; do
        [[ -f "$SOURCE_DIR/$relative_path" ]] || \
            fail "Required source file missing: $SOURCE_DIR/$relative_path"
    done

    if [[ -n "$CREDENTIAL_SOURCE" ]]; then
        CREDENTIAL_SOURCE="$(readlink -f -- "$CREDENTIAL_SOURCE")"
        [[ -f "$CREDENTIAL_SOURCE" ]] || \
            fail "Credential file not found: $CREDENTIAL_SOURCE"
        PYTHONPATH="$SOURCE_DIR" python3 - "$CREDENTIAL_SOURCE" <<'PY'
import sys

from web_auth import CredentialStore

credential_file = sys.argv[1]
if not CredentialStore(credential_file).is_configured():
    raise SystemExit(f"Credential file is invalid: {credential_file}")
PY
    fi

    python3 -m py_compile \
        "$SOURCE_DIR/actions/scanning.py" \
        "$SOURCE_DIR/Bjorn.py" \
        "$SOURCE_DIR/display.py" \
        "$SOURCE_DIR/epd_helper.py" \
        "$SOURCE_DIR/web_auth.py" \
        "$SOURCE_DIR/configure_web_auth.py" \
        "$SOURCE_DIR/webapp.py" \
        "$SOURCE_DIR/shared.py"
fi

TARGET_OWNER="$(stat -c '%U' -- "$TARGET_DIR")"
TARGET_GROUP="$(stat -c '%G' -- "$TARGET_DIR")"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ROLLBACK_DIR="$(
    mktemp -d "$ROLLBACK_ROOT/stability-web-auth-rollback-$TIMESTAMP-XXXXXX"
)"
mkdir -p "$ROLLBACK_DIR/files"

MANAGED_PATHS=(
    actions/scanning.py
    Bjorn.py
    display.py
    epd_helper.py
    webapp.py
    shared.py
    web_auth.py
    configure_web_auth.py
    config/web_auth.json
    .gitignore
)

for relative_path in "${MANAGED_PATHS[@]}"; do
    if [[ -e "$TARGET_DIR/$relative_path" ]]; then
        mkdir -p "$ROLLBACK_DIR/files/$(dirname -- "$relative_path")"
        cp -a -- "$TARGET_DIR/$relative_path" \
            "$ROLLBACK_DIR/files/$relative_path"
    else
        printf '%s\n' "$relative_path" >>"$ROLLBACK_DIR/absent-before-install.txt"
    fi
done

if [[ -e "$COMMAND_PATH" || -L "$COMMAND_PATH" ]]; then
    mkdir -p "$ROLLBACK_DIR/system-command"
    cp -a -- "$COMMAND_PATH" "$ROLLBACK_DIR/system-command/value"
else
    touch "$ROLLBACK_DIR/system-command-absent"
fi

validate_snapshot() {
    local snapshot_dir="$1"
    local relative_path
    local saved
    local absent

    [[ -d "$snapshot_dir/files" ]] || \
        fail "Snapshot has no files directory: $snapshot_dir"

    for relative_path in "${MANAGED_PATHS[@]}"; do
        saved=0
        absent=0
        [[ -e "$snapshot_dir/files/$relative_path" || \
           -L "$snapshot_dir/files/$relative_path" ]] && saved=1
        if [[ -f "$snapshot_dir/absent-before-install.txt" ]] && \
           grep -qxF "$relative_path" \
               "$snapshot_dir/absent-before-install.txt"; then
            absent=1
        fi
        ((saved + absent == 1)) || \
            fail "Snapshot state is incomplete for: $relative_path"
    done

    saved=0
    absent=0
    [[ -e "$snapshot_dir/system-command/value" || \
       -L "$snapshot_dir/system-command/value" ]] && saved=1
    [[ -f "$snapshot_dir/system-command-absent" ]] && absent=1
    ((saved + absent == 1)) || \
        fail "Snapshot state is incomplete for: $COMMAND_PATH"
}

restore_snapshot() {
    local snapshot_dir="$1"
    local relative_path
    local saved_path
    info "Restoring snapshot from: $snapshot_dir"

    for relative_path in "${MANAGED_PATHS[@]}"; do
        saved_path="$snapshot_dir/files/$relative_path"
        if [[ -e "$saved_path" || -L "$saved_path" ]]; then
            mkdir -p "$TARGET_DIR/$(dirname -- "$relative_path")"
            rm -f -- "$TARGET_DIR/$relative_path"
            cp -a -- "$saved_path" "$TARGET_DIR/$relative_path"
        else
            rm -f -- "$TARGET_DIR/$relative_path"
        fi
    done

    rm -f -- "$COMMAND_PATH"
    if [[ -e "$snapshot_dir/system-command/value" || \
          -L "$snapshot_dir/system-command/value" ]]; then
        mkdir -p "$(dirname -- "$COMMAND_PATH")"
        cp -a -- "$snapshot_dir/system-command/value" "$COMMAND_PATH"
    fi
}

wait_for_web_port_release() {
    local webapp_file="$TARGET_DIR/webapp.py"
    local second
    local reuse_address=0

    if [[ -f "$webapp_file" ]] && \
       grep -Eq 'allow_reuse_address[[:space:]]*=[[:space:]]*True' \
           "$webapp_file"; then
        reuse_address=1
    fi

    for ((second = 0; second <= PORT_RELEASE_TIMEOUT; second++)); do
        if python3 - "$WEB_PORT" "$reuse_address" <<'PY'
import socket
import sys

port = int(sys.argv[1])
reuse_address = bool(int(sys.argv[2]))
probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    if reuse_address:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    probe.bind(("", port))
except OSError:
    raise SystemExit(1)
finally:
    probe.close()
PY
        then
            success "Port $WEB_PORT is available"
            return 0
        fi
        if ((second % 5 == 0)); then
            info "Waiting for port $WEB_PORT release: " \
                 "$second/$PORT_RELEASE_TIMEOUT seconds"
        fi
        sleep 1
    done

    fail "Port $WEB_PORT did not become available within " \
         "$PORT_RELEASE_TIMEOUT seconds."
}

start_and_verify() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        fail "$SERVICE_NAME must be inactive before startup verification."
        return 1
    fi

    wait_for_web_port_release
    systemctl reset-failed "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    HTTP_STATUS=""
    for _ in {1..30}; do
        HTTP_STATUS="$(
            curl --silent --output /dev/null --write-out '%{http_code}' \
                --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
        )"
        if [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "401" ]]; then
            break
        fi
        sleep 1
    done
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        fail "$SERVICE_NAME did not remain active."
        return 1
    fi
    if [[ "$HTTP_STATUS" != "200" && "$HTTP_STATUS" != "401" ]]; then
        fail "Web interface on port $WEB_PORT is not ready " \
             "(HTTP $HTTP_STATUS)."
        return 1
    fi
}

stop_before_restore() {
    local stop_result=0

    systemctl stop "$SERVICE_NAME" || stop_result=$?
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        fail "$SERVICE_NAME is still active; refusing to restore files."
        return 1
    fi
    if pgrep -f -- "$TARGET_DIR/Bjorn.py" >/dev/null; then
        fail "A target Bjorn.py process remains; refusing to restore files."
        return 1
    fi
    if ((stop_result != 0)); then
        warning "systemctl stop returned $stop_result, " \
                "but no Bjorn process remains"
    fi
}

on_exit() {
    local exit_code=$?
    if ((exit_code != 0 && INSTALL_STARTED == 1)); then
        set +e
        error "Operation failed; stopping the attempted deployment"
        if stop_before_restore; then
            restore_snapshot "$ROLLBACK_DIR"
            if start_and_verify; then
                success "Previous files and HTTP endpoint restored"
                printf 'Machine marker: RECOVERY_OK\n' >&2
            else
                error "RECOVERY_FAILED: files were restored, but the service " \
                      "or HTTP endpoint needs attention"
            fi
        else
            error "RECOVERY_ABORTED: the attempted service is still running; " \
                  "files were not overwritten"
        fi
    fi
    exit "$exit_code"
}
trap on_exit EXIT

if [[ -n "$RESTORE_SOURCE" ]]; then
    validate_snapshot "$RESTORE_SOURCE"
fi

success "Inputs and source files validated"
info "Recovery snapshot: $ROLLBACK_DIR"

step 2 5 "Stop the running Bjorn service"
INSTALL_STARTED=1
set +e
systemctl stop "$SERVICE_NAME"
STOP_RESULT=$?
set -e

if systemctl is-active --quiet "$SERVICE_NAME"; then
    fail "$SERVICE_NAME is still active after stop (exit $STOP_RESULT)."
fi
if pgrep -f -- "$TARGET_DIR/Bjorn.py" >/dev/null; then
    fail "A Bjorn.py process from the target directory is still running."
fi
if ((STOP_RESULT != 0)); then
    warning "systemctl stop returned $STOP_RESULT, but no Bjorn process remains"
fi
success "$SERVICE_NAME stopped and no target process remains"

if [[ -n "$RESTORE_SOURCE" ]]; then
    step 3 5 "Restore the selected snapshot"
    restore_snapshot "$RESTORE_SOURCE"
    RESTORED_PYTHON_FILES=(
        "$TARGET_DIR/actions/scanning.py"
        "$TARGET_DIR/Bjorn.py"
        "$TARGET_DIR/display.py"
        "$TARGET_DIR/epd_helper.py"
        "$TARGET_DIR/webapp.py"
        "$TARGET_DIR/shared.py"
    )
    [[ -f "$TARGET_DIR/web_auth.py" ]] && \
        RESTORED_PYTHON_FILES+=("$TARGET_DIR/web_auth.py")
    [[ -f "$TARGET_DIR/configure_web_auth.py" ]] && \
        RESTORED_PYTHON_FILES+=("$TARGET_DIR/configure_web_auth.py")
    python3 -m py_compile "${RESTORED_PYTHON_FILES[@]}"
    success "Snapshot restored and Python files compiled"

    step 4 5 "Start and verify the restored service"
    start_and_verify
    success "$SERVICE_NAME is active; web interface returned HTTP $HTTP_STATUS"

    INSTALL_STARTED=0
    trap - EXIT

    step 5 5 "Complete rollback"
    complete "Rollback completed successfully"
    summary_row "Service:" \
        "$SERVICE_NAME ($(systemctl is-active "$SERVICE_NAME"))"
    summary_row "Web interface:" "HTTP $HTTP_STATUS on port $WEB_PORT"
    summary_row "Restored snapshot:" "$RESTORE_SOURCE"
    summary_row "Recovery snapshot:" "$ROLLBACK_DIR"
    printf '%bMachine marker: RESTORE_OK%b\n' "$DIM" "$NC"
    exit 0
fi

step 3 5 "Install stability and web-auth files"
if [[ "$SOURCE_DIR" != "$TARGET_DIR" ]]; then
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/actions/scanning.py" \
        "$TARGET_DIR/actions/scanning.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/Bjorn.py" "$TARGET_DIR/Bjorn.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/display.py" "$TARGET_DIR/display.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/epd_helper.py" "$TARGET_DIR/epd_helper.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/webapp.py" "$TARGET_DIR/webapp.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/shared.py" "$TARGET_DIR/shared.py"
    install -m 644 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/web_auth.py" "$TARGET_DIR/web_auth.py"
    install -m 755 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
        "$SOURCE_DIR/configure_web_auth.py" \
        "$TARGET_DIR/configure_web_auth.py"
fi

touch "$TARGET_DIR/.gitignore"
if ! grep -qxF 'config/web_auth.json' "$TARGET_DIR/.gitignore"; then
    printf '\nconfig/web_auth.json\n' >>"$TARGET_DIR/.gitignore"
fi
chown "$TARGET_OWNER:$TARGET_GROUP" "$TARGET_DIR/.gitignore"

if [[ -n "$CREDENTIAL_SOURCE" ]]; then
    TARGET_CREDENTIAL_FILE="$(readlink -m -- "$TARGET_DIR/config/web_auth.json")"
    if [[ "$CREDENTIAL_SOURCE" != "$TARGET_CREDENTIAL_FILE" ]]; then
        install -m 600 -o "$TARGET_OWNER" -g "$TARGET_GROUP" \
            "$CREDENTIAL_SOURCE" "$TARGET_CREDENTIAL_FILE"
    else
        chmod 600 "$TARGET_CREDENTIAL_FILE"
        chown "$TARGET_OWNER:$TARGET_GROUP" "$TARGET_CREDENTIAL_FILE"
    fi
elif [[ -n "$USERNAME" ]]; then
    python3 "$TARGET_DIR/configure_web_auth.py" set "$USERNAME"
fi

if [[ -d "$COMMAND_PATH" && ! -L "$COMMAND_PATH" ]]; then
    fail "Command path is an existing directory: $COMMAND_PATH"
fi
install -d -m 755 "$(dirname -- "$COMMAND_PATH")"
ln -sfn -- "$TARGET_DIR/configure_web_auth.py" "$COMMAND_PATH"
success "Runtime files, credentials, and management command installed"

step 4 5 "Compile, start, and verify the service"
python3 -m py_compile \
    "$TARGET_DIR/actions/scanning.py" \
    "$TARGET_DIR/Bjorn.py" \
    "$TARGET_DIR/display.py" \
    "$TARGET_DIR/epd_helper.py" \
    "$TARGET_DIR/web_auth.py" \
    "$TARGET_DIR/configure_web_auth.py" \
    "$TARGET_DIR/webapp.py" \
    "$TARGET_DIR/shared.py"

start_and_verify
success "$SERVICE_NAME is active; web interface returned HTTP $HTTP_STATUS"

INSTALL_STARTED=0
trap - EXIT

step 5 5 "Complete installation"
complete "Installation completed successfully"
summary_row "Service:" \
    "$SERVICE_NAME ($(systemctl is-active "$SERVICE_NAME"))"
summary_row "Web interface:" "HTTP $HTTP_STATUS on port $WEB_PORT"
summary_row "Rollback snapshot:" "$ROLLBACK_DIR"
summary_row "Management command:" "$COMMAND_PATH"
if [[ -z "$CREDENTIAL_SOURCE" && -z "$USERNAME" ]]; then
    warning "Authentication is not configured yet"
    info "Run: sudo http_auth set <username>"
fi
printf '%bMachine marker: INSTALL_OK%b\n' "$DIM" "$NC"
