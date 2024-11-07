#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging configuration
LOG_DIR="/var/log/bjorn_remove"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/bjorn_remove_$(date +%Y%m%d_%H%M%S).log"

# Logging function
log() {
    local level=$1
    shift
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
    echo -e "$message" >> "$LOG_FILE"
    case $level in
        "ERROR") echo -e "${RED}$message${NC}" ;;
        "SUCCESS") echo -e "${GREEN}$message${NC}" ;;
        "WARNING") echo -e "${YELLOW}$message${NC}" ;;
        "INFO") echo -e "${BLUE}$message${NC}" ;;
        *) echo -e "$message" ;;
    esac
}

# Function to ask for confirmation
confirm() {
    echo -e "${YELLOW}Do you want to $1? (y/n)${NC}"
    read -r response
    case "$response" in
        [yY]) return 0 ;;
        *) return 1 ;;
    esac
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    log "ERROR" "This script must be run as root. Please use 'sudo'."
    exit 1
fi

# Function to stop services
stop_services() {
    log "INFO" "Stopping services..."
    
    # Kill any running BJORN processes
    if pgrep -f "python3 /home/bjorn/Bjorn/Bjorn.py" > /dev/null; then
        log "INFO" "Killing BJORN Python process..."
        pkill -f "python3 /home/bjorn/Bjorn/Bjorn.py"
    fi

    # Stop and disable bjorn service
    if systemctl is-active --quiet "bjorn"; then
        log "INFO" "Stopping bjorn service..."
        systemctl stop bjorn
        systemctl disable bjorn
    fi

    # Stop and disable usb-gadget service
    if systemctl is-active --quiet "usb-gadget"; then
        log "INFO" "Stopping usb-gadget service..."
        systemctl stop usb-gadget
        systemctl disable usb-gadget
    fi

    # Kill any processes on port 8000
    if lsof -i:8000 > /dev/null; then
        log "INFO" "Killing processes on port 8000..."
        lsof -ti:8000 | xargs kill -9
    fi

    log "SUCCESS" "All services stopped"
}

# Function to remove service files
remove_service_files() {
    log "INFO" "Removing service files..."
    rm -f /etc/systemd/system/bjorn.service
    rm -f /etc/systemd/system/usb-gadget.service
    rm -f /usr/local/bin/usb-gadget.sh
    systemctl daemon-reload
    log "SUCCESS" "Service files removed"
}

# Function to reset USB gadget configuration
reset_usb_config() {
    log "INFO" "Resetting USB gadget configuration..."
    
    # Reset cmdline.txt
    if [ -f /boot/firmware/cmdline.txt ]; then
        sed -i 's/ modules-load=dwc2,g_ether//' /boot/firmware/cmdline.txt
    fi
    
    # Reset config.txt
    if [ -f /boot/firmware/config.txt ]; then
        sed -i '/dtoverlay=dwc2/d' /boot/firmware/config.txt
    fi
    
    # Remove USB network configuration
    sed -i '/allow-hotplug usb0/,+3d' /etc/network/interfaces
    
    log "SUCCESS" "USB configuration reset"
}

# Function to reset system limits
reset_system_limits() {
    log "INFO" "Resetting system limits..."
    
    # Remove from limits.conf
    sed -i '/\* soft nofile 65535/d' /etc/security/limits.conf
    sed -i '/\* hard nofile 65535/d' /etc/security/limits.conf
    sed -i '/root soft nofile 65535/d' /etc/security/limits.conf
    sed -i '/root hard nofile 65535/d' /etc/security/limits.conf
    
    # Remove limits file
    rm -f /etc/security/limits.d/90-nofile.conf
    
    # Reset systemd limits
    sed -i 's/DefaultLimitNOFILE=65535/#DefaultLimitNOFILE=/' /etc/systemd/system.conf
    sed -i 's/DefaultLimitNOFILE=65535/#DefaultLimitNOFILE=/' /etc/systemd/user.conf
    
    # Reset sysctl
    sed -i '/fs.file-max = 2097152/d' /etc/sysctl.conf
    sysctl -p
    
    log "SUCCESS" "System limits reset"
}

# Function to remove BJORN files
remove_bjorn_files() {
    log "INFO" "Removing BJORN files..."
    if [ -d "/home/bjorn/Bjorn" ]; then
        rm -rf /home/bjorn/Bjorn
        log "SUCCESS" "BJORN directory removed"
    else
        log "INFO" "BJORN directory not found"
    fi
}

# Main execution
echo -e "${BLUE}BJORN Removal Script${NC}"
echo -e "${YELLOW}This script will remove BJORN while preserving the bjorn user and system packages.${NC}"
echo -e "${YELLOW}Each step will ask for confirmation before proceeding.${NC}"

# Step 1: Stop Services
if confirm "stop all BJORN related services"; then
    stop_services
fi

# Step 2: Remove Service Files
if confirm "remove BJORN service files"; then
    remove_service_files
fi

# Step 3: Reset USB Configuration
if confirm "reset USB gadget configuration"; then
    reset_usb_config
fi

# Step 4: Reset System Limits
if confirm "reset system limits"; then
    reset_system_limits
fi

# Step 5: Remove BJORN Files
if confirm "remove BJORN files (keeping bjorn user)"; then
    remove_bjorn_files
fi

# Final summary
echo -e "\n${GREEN}BJORN removal completed!${NC}"
echo -e "${BLUE}Summary of actions:${NC}"
echo "1. Services stopped and disabled"
echo "2. Service files removed"
echo "3. USB configuration reset"
echo "4. System limits reset"
echo "5. BJORN files removed"
echo -e "\n${YELLOW}Preserved:${NC}"
echo "- bjorn user account"
echo "- System packages"
echo "- Python packages"
echo "- SPI and I2C configurations"

# Ask for reboot
if confirm "reboot the system now"; then
    log "INFO" "System rebooting..."
    reboot
else
    echo -e "${YELLOW}Please reboot your system manually when convenient.${NC}"
fi

log "SUCCESS" "Script completed"
echo -e "${BLUE}Log file available at: $LOG_FILE${NC}"