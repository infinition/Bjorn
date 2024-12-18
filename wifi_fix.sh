#!/bin/bash
# Author : Infinition

# Log file
LOG_FILE="/var/log/wifi-manager.log"

# Array to track failed operations
declare -a failed_apt_packages

# Logging function
log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" >> "$LOG_FILE"
}

manage_wifi_connections() {
    log "INFO" "Managing Wi-Fi connections..."

    PRECONFIG_FILE="/etc/NetworkManager/system-connections/preconfigured.nmconnection"

    if [ -f "$PRECONFIG_FILE" ]; then
        log "INFO" "Extracting data from preconfigured Wi-Fi connection..."

        # Extract SSID
        SSID=$(grep '^ssid=' "$PRECONFIG_FILE" | cut -d'=' -f2)

        # Extract PSK
        PSK=$(grep '^psk=' "$PRECONFIG_FILE" | cut -d'=' -f2)

        if [ -z "$SSID" ]; then
            log "ERROR" "SSID not found in preconfigured file."
            echo -e "${RED}SSID not found in preconfigured Wi-Fi file. Check the log for details.${NC}"
            failed_apt_packages+=("SSID extraction from preconfigured Wi-Fi")
            return 1
        fi

        # Create a new connection named after the SSID with priority 5
        log "INFO" "Creating new Wi-Fi connection for SSID: $SSID with priority 5"
        if nmcli connection add type wifi ifname wlan0 con-name "$SSID" ssid "$SSID" \
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" connection.autoconnect yes \
            connection.autoconnect-priority 5 >> "$LOG_FILE" 2>&1; then
            log "SUCCESS" "Created new Wi-Fi connection for SSID: $SSID"
        else
            log "ERROR" "Failed to create Wi-Fi connection for SSID: $SSID"
            echo -e "${RED}Failed to create Wi-Fi connection for SSID: $SSID. Check the log for details.${NC}"
            failed_apt_packages+=("Wi-Fi connection for SSID: $SSID")
        fi

        # Remove preconfigured file only after successful creation of new connections
        rm "$PRECONFIG_FILE"
        if [ $? -eq 0 ]; then
            log "SUCCESS" "Removed preconfigured Wi-Fi connection file."
        else
            log "WARNING" "Failed to remove preconfigured Wi-Fi connection file."
        fi
    else
        log "WARNING" "No preconfigured Wi-Fi connection file found."
    fi
}

# Main execution
manage_wifi_connections