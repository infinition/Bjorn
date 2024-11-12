# <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="33"> Bjorn

[![Reddit](https://img.shields.io/badge/Reddit-Bjorn__CyberViking-orange?style=for-the-badge&logo=reddit)](https://www.reddit.com/r/Bjorn_CyberViking)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289DA?style=for-the-badge&logo=discord)](https://discord.com/invite/B3ZH9taVfT)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<p align="center">
  <img src="https://github.com/user-attachments/assets/c5eb4cc1-0c3d-497d-9422-1614651a84ab" alt="thumbnail_IMG_0546" width="150">
  <img src="https://github.com/user-attachments/assets/1b490f07-f28e-4418-8d41-14f1492890c6" alt="bjorn_epd-removebg-preview" width="150">
</p>

Bjorn is a « Tamagotchi like » sophisticated, autonomous network scanning, vulnerability assessment, and offensive security tool designed to run on a Raspberry Pi equipped with a 2.13-inch e-Paper HAT. This document provides a detailed explanation of the project.


## 📚 Table of Contents

- [Features](#-features)
- [Design](#design)
- [Educational Aspects](#educational-aspects)
- [Disclaimer](#disclaimer)
- [Extensibility](#extensibility)
- [Development Status](#development-status)
- [Detailed Project Description](#detailed-project-description)
  - [Project Structure](#project-structure)
  - [Core Files](#core-files)
  - [Actions](#actions)
  - [Data Structure](#data-structure)
  - [Behavior of Bjorn](#behavior-of-bjorn)
- [Installation and Configuration](#installation-and-configuration)
  - [Prerequisites](#prerequisites)
  - [Quick Installation](#quick-installation)
  - [Manual Installation](#manual-installation)
    - [Step 1: Activate SPI & I2C](#step-1-activate-spi--i2c)
    - [Step 2: System Dependencies](#step-2-system-dependencies)
    - [Step 3: Bjorn Installation](#step-3-bjorn-installation)
    - [Step 4: Configure File Descriptor Limits](#step-4-configure-file-descriptor-limits)
    - [Step 5: Reload Systemd and Apply Changes](#step-5-reload-systemd-and-apply-changes)
    - [Step 6: Modify PAM Configuration Files](#step-6-modify-pam-configuration-files)
    - [Step 7: Configure Services](#step-7-configure-services)
- [Running Bjorn](#running-bjorn)
  - [Manual Start](#manual-start)
  - [Service Control](#service-control)
  - [Fresh Start](#fresh-start)
- [Important Configuration Files](#important-configuration-files)
  - [Shared Configuration (`shared_config.json`)](#shared-configuration-shared_configjson)
  - [Actions Configuration (`actions.json`)](#actions-configuration-actionsjson)
- [Known Issues and Troubleshooting](#known-issues-and-troubleshooting)
  - [Current Development Issues](#current-development-issues)
  - [Troubleshooting Steps](#troubleshooting-steps)
- [E-Paper Display Support](#e-paper-display-support)
- [Development Guidelines](#development-guidelines)
  - [Adding New Actions](#adding-new-actions)
  - [Testing](#testing)
- [Web Interface](#web-interface)
- [Project Roadmap](#project-roadmap)
  - [Current Focus](#current-focus)
  - [Future Plans](#future-plans)
- [Contributing](#contributing)
- [Support and Contact](#support-and-contact)
- [Conclusion](#conclusion)
- [License](#-license)
- [Contact](#-contact)

## 🌟 Features

- **Network Scanning**: Identifies live hosts and open ports on the network.
- **Vulnerability Assessment**: Performs vulnerability scans using Nmap and other tools.
- **System Attacks**: Conducts brute-force attacks on various services (FTP, SSH, SMB, RDP, Telnet, SQL).
- **File Stealing**: Extracts data from vulnerable services.
- **User Interface**: Real-time display on the e-Paper HAT and web interface for monitoring and interaction.

[↖️](#table-of-contents) 
## Design

- **Portability**: Self-contained and portable device, ideal for penetration testing.
- **Modularity**: Extensible architecture allowing  addition of new actions.
- **Visual Interface**: The e-Paper HAT provides a visual interface for monitoring the ongoing actions, displaying results or stats, and interacting with Bjorn .

[↖️](#table-of-contents) 
## Educational Aspects

- **Learning Tool**: Designed as an educational tool to understand cybersecurity concepts and penetration testing techniques.
- **Practical Experience**: Provides a practical means for students and professionals to familiarize themselves with network security practices and vulnerability assessment tools.

[↖️](#table-of-contents) 
## Disclaimer

- **Ethical Use**: This project is strictly for educational purposes.
- **Responsibility**: The author and contributors disclaim any responsibility for misuse of Bjorn.
- **Legal Compliance**: Unauthorized use of this tool for malicious activities is prohibited and may be prosecuted by law.

[↖️](#table-of-contents) 
## Extensibility

- **Evolution**: The main purpose of Bjorn is to gain new actions and extend his arsenal over time.
- **Modularity**: Actions are designed to be modular and can be easily extended or modified to add new functionality.
- **Possibilities**: From capturing pcap files to cracking hashes, man-in-the-middle attacks, and more—the possibilities are endless.
- **Contribution**: It's up to the user to develop new actions and add them to the project.

[↖️](#table-of-contents) 
## Development Status

- **Project Status**: Ongoing development.
- **Current Version**: Scripted  auto-installer, or manual installation. Not yet packaged with Raspberry Pi OS.
- **Reason**: The project is still in an early stage, requiring further development and debugging.


![Bjorn Display](https://github.com/infinition/Bjorn/assets/37984399/bcad830d-77d6-4f3e-833d-473eadd33921)

---

[↖️](#table-of-contents) 
## Detailed Project Description

[↖️](#table-of-contents) 
### Project Structure

```
Bjorn/
├── Bjorn.py
├── comment.py
├── display.py
├── epd_helper.py
├── init_shared.py
├── kill_port_8000.sh
├── logger.py
├── orchestrator.py
├── requirements.txt
├── shared.py
├── utils.py
├── webapp.py
├── __init__.py
├── actions/
│   ├── ftp_connector.py
│   ├── ssh_connector.py
│   ├── smb_connector.py
│   ├── rdp_connector.py
│   ├── telnet_connector.py
│   ├── sql_connector.py
│   ├── steal_files_ftp.py
│   ├── steal_files_ssh.py
│   ├── steal_files_smb.py
│   ├── steal_files_rdp.py
│   ├── steal_files_telnet.py
│   ├── steal_data_sql.py
│   ├── nmap_vuln_scanner.py
│   ├── scanning.py
│   └── __init__.py
├── backup/
│   ├── backups/
│   └── uploads/
├── config/
├── data/
│   ├── input/
│   │   └── dictionary/
│   ├── logs/
│   └── output/
│       ├── crackedpwd/
│       ├── data_stolen/
│       ├── scan_results/
│       ├── vulnerabilities/
│       └── zombies/
└── resources/
    └── waveshare_epd/
```

[↖️](#table-of-contents) 
### Core Files

#### Bjorn.py

The main entry point for the application. It initializes and runs the main components, including the network scanner, orchestrator, display, and web server.

#### comment.py

Handles generating all the Bjorn comments displayed on the e-Paper HAT based on different themes/actions and statuses.

#### display.py

Manages the e-Paper HAT display, updating the screen with Bjorn character, the dialog/comments, and the current information such as network status, vulnerabilities, and various statistics.

#### epd_helper.py

Handles the low-level interactions with the e-Paper display hardware.

#### logger.py

Defines a custom logger with specific formatting and handlers for console and file logging. It also includes a custom log level for success messages.

#### orchestrator.py

Bjorn’s AI, an heuristic engine that orchestrates the different actions such as network scanning, vulnerability scanning, attacks, and file stealing. It loads and executes actions based on the configuration and sets the status of the actions and Bjorn. 

#### shared.py

Defines the `SharedData` class that holds configuration settings, paths, and methods for updating and managing shared data across different modules.

#### init_shared.py

Initializes shared data that is used across different modules. It loads the configuration and sets up necessary paths and variables.

#### utils.py

Contains utility functions used throughout the project.

#### webapp.py

Sets up and runs a web server to provide a web interface for changing settings, monitoring and interacting with Bjorn.

[↖️](#table-of-contents) 
### Actions

#### actions/scanning.py

Conducts network scanning to identify live hosts and open ports. It updates the network knowledge base (`netkb`) and generates scan results.

#### actions/nmap_vuln_scanner.py

Performs vulnerability scanning using Nmap. It parses the results and updates the vulnerability summary for each host.

#### Protocol Connectors

- **ftp_connector.py**: Brute-force attacks on FTP services.
- **ssh_connector.py**: Brute-force attacks on SSH services.
- **smb_connector.py**: Brute-force attacks on SMB services.
- **rdp_connector.py**: Brute-force attacks on RDP services.
- **telnet_connector.py**: Brute-force attacks on Telnet services.
- **sql_connector.py**: Brute-force attacks on SQL services.

#### File Stealing Modules

- **steal_files_ftp.py**: Steals files from FTP servers.
- **steal_files_smb.py**: Steals files from SMB shares.
- **steal_files_ssh.py**: Steals files from SSH servers.
- **steal_files_telnet.py**: Steals files from Telnet servers.
- **steal_data_sql.py**: Extracts data from SQL databases.

[↖️](#table-of-contents) 
### Data Structure

#### Network Knowledge Base (netkb.csv)

Located at `data/netkb.csv`. Stores information about:

- Known hosts and their status. (Alive or offline)
- Open ports and vulnerabilities.
- Action execution history. (Success or failed)

**Preview Example:**

![netkb1](https://github.com/infinition/Bjorn/assets/37984399/f641a565-2765-4280-a7d7-5b25c30dcea5)
![netkb2](https://github.com/infinition/Bjorn/assets/37984399/f08114a2-d7d1-4f50-b1c4-a9939ba66056)

#### Scan Results

Located in `data/output/scan_results/`.
This file is generated everytime the network is scanned. It is used to consolidate the data and update netkb.

**Example:**

![Scan result](https://github.com/infinition/Bjorn/assets/37984399/eb4a313a-f90c-4c43-b699-3678271886dc)

#### Live Status (livestatus.csv)

Contains real-time information displayed on the e-Paper HAT:

- Total number of known hosts.
- Currently alive hosts.
- Open ports count.
- Other runtime statistics.

[↖️](#table-of-contents) 
### Behavior of Bjorn

Once launched, Bjorn performs the following steps:

1. **Initialization**: Loads configuration, initializes shared data, and sets up necessary components such as the e-Paper HAT display.
2. **Network Scanning**: Scans the network to identify live hosts and open ports. Updates the network knowledge base (`netkb`) with the results.
3. **Orchestration**: Orchestrates different actions based on the configuration and network knowledge base. This includes performing vulnerability scanning, attacks, and file stealing.
4. **Vulnerability Scanning**: Performs vulnerability scans on identified hosts and updates the vulnerability summary.
5. **Brute-Force Attacks and File Stealing**: Starts brute-force attacks and steals files based on the configuration criteria.
6. **Display Updates**: Continuously updates the e-Paper HAT display with current information such as network status, vulnerabilities, and various statistics. Bjorn also displays random comments based on different themes and statuses.
7. **Web Server**: Provides a web interface for monitoring and interacting with Bjorn.

---




[↖️](#table-of-contents) 
## Installation and Configuration
Use Raspberry Pi Imager to install your OS
https://www.raspberrypi.com/software/

### Prerequisites

![image](https://github.com/user-attachments/assets/e775f454-1771-4d6c-bff5-b262b3d98452)

- Raspberry Pi OS installed. 
    - Stable:
      - System: 32-bit
      - Kernel version: 6.6
      - Debian version: 12 (bookworm) '2024-10-22-raspios-bookworm-armhf-lite'
- Username and hostname set to `bjorn`.
- 2.13-inch e-Paper HAT connected to GPIO pins.

At the moment the paper screen v2 & v4 have been tested and implemented.
I juste hope the V1 & V3 will work the same.

### Need help ? You struggle to find Bjorn's IP after the installation ?
Use my Bjorn Detector & SSH Launcher :

https://github.com/infinition/Bjorn_Detector

![ezgif-1-a310f5fe8f](https://github.com/user-attachments/assets/182f82f0-5c3a-48a9-a75e-37b9cfa2263a)

[↖️](#table-of-contents) 
### Quick Installation

The fastest way to install Bjorn is using the automatic installation script :

```bash
# Download and run the installer
wget https://raw.githubusercontent.com/infinition/Bjorn/refs/heads/main/install_bjorn.sh
sudo chmod +x install_bjorn.sh
sudo ./install_bjorn.sh
# Choose the choice 1 for automatic installation. It may take a while as a lot of packages and modules will be installed. You must reboot at the end.
```

[↖️](#table-of-contents) 
### Manual Installation



#### Step 1: Activate SPI & I2C

```bash
sudo raspi-config
```

- Navigate to **"Interface Options"**.
- Enable **SPI**.
- Enable **I2C**.

#### Step 2: System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install required packages

 sudo apt install -y \
  libjpeg-dev \
  zlib1g-dev \
  libpng-dev \
  python3-dev \
  libffi-dev \
  libssl-dev \
  libgpiod-dev \
  libi2c-dev \
  libatlas-base-dev \
  build-essential \
  python3-pip \
  wget \
  lsof \
  git \
  libopenjp2-7 \
  nmap \
  libopenblas-dev \
  bluez-tools \
  bluez \
  dhcpcd5 \
  bridge-utils \
  python3-pil


# Update Nmap scripts database

sudo nmap --script-updatedb

```

#### Step 3: Bjorn Installation

```bash
# Clone the Bjorn repository
cd /home/bjorn
git clone https://github.com/infinition/Bjorn.git
cd Bjorn

# Install Python dependencies within the virtual environment
sudo pip install -r requirements.txt --break-system-packages
# As i did not succeed "for now" to get a stable installation with a virtual environment, i installed the dependencies system wide (with --break-system-packages), it did not cause any issue so far. You can try to install them in a virtual environment if you want.
```

##### 3.1: Configure E-Paper Display Type
Choose your e-Paper HAT version by modifying the configuration file:

1. Open the configuration file:
```bash
sudo vi /home/bjorn/Bjorn/config/shared_config.json
```
Press i to enter insert mode
Locate the line containing "epd_type":
Change the value according to your screen model:

- For 2.13 V1: "epd_type": "epd2in13",
- For 2.13 V2: "epd_type": "epd2in13_V2",
- For 2.13 V3: "epd_type": "epd2in13_V3",
- For 2.13 V4: "epd_type": "epd2in13_V4",

Press Esc to exit insert mode
Type :wq and press Enter to save and quit

#### Step 4: Configure File Descriptor Limits

To prevent `OSError: [Errno 24] Too many open files`, it's essential to increase the file descriptor limits.

##### 4.1: Modify File Descriptor Limits for All Users

Edit `/etc/security/limits.conf`:

```bash
sudo vi /etc/security/limits.conf
```

Add the following lines:

```
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
```

##### 4.2: Configure Systemd Limits

Edit `/etc/systemd/system.conf`:

```bash
sudo vi /etc/systemd/system.conf
```

Uncomment and modify:

```
DefaultLimitNOFILE=65535
```

Edit `/etc/systemd/user.conf`:

```bash
sudo vi /etc/systemd/user.conf
```

Uncomment and modify:

```
DefaultLimitNOFILE=65535
```

##### 4.3: Create or Modify `/etc/security/limits.d/90-nofile.conf`

```bash
sudo vi /etc/security/limits.d/90-nofile.conf
```

Add:

```
root soft nofile 65535
root hard nofile 65535
```

##### 4.4: Adjust the System-wide File Descriptor Limit

Edit `/etc/sysctl.conf`:

```bash
sudo vi /etc/sysctl.conf
```

Add:

```
fs.file-max = 2097152
```

Apply the changes:

```bash
sudo sysctl -p
```

#### Step 5: Reload Systemd and Apply Changes

Reload systemd to apply the new file descriptor limits:

```bash
sudo systemctl daemon-reload
```

#### Step 6: Modify PAM Configuration Files

PAM (Pluggable Authentication Modules) manages how limits are enforced for user sessions. To ensure that the new file descriptor limits are respected, update the following configuration files.

##### Step 6.1: Edit `/etc/pam.d/common-session` and `/etc/pam.d/common-session-noninteractive`

```bash
sudo vi /etc/pam.d/common-session
sudo vi /etc/pam.d/common-session-noninteractive
```

Add this line at the end of both files:

```
session required pam_limits.so
```

This ensures that the limits set in `/etc/security/limits.conf` are enforced for all user sessions.

#### Step 7: Configure Services

##### 7.1: Bjorn Service

Create the service file:

```bash
sudo vi /etc/systemd/system/bjorn.service
```

Add the following content:

```ini
[Unit]
Description=Bjorn Service
DefaultDependencies=no
Before=basic.target
After=local-fs.target

[Service]
ExecStartPre=/home/bjorn/Bjorn/kill_port_8000.sh
ExecStart=/usr/bin/python3 /home/bjorn/Bjorn/Bjorn.py
WorkingDirectory=/home/bjorn/Bjorn
StandardOutput=inherit
StandardError=inherit
Restart=always
User=root

[Install]
WantedBy=multi-user.target
```



##### 7.2: Port 8000 Killer Script

Create the script to free up port 8000:

```bash
vi /home/bjorn/Bjorn/kill_port_8000.sh
```

Add:

```bash
#!/bin/bash
PORT=8000
PIDS=$(lsof -t -i:$PORT)

if [ -n "$PIDS" ]; then
    echo "Killing PIDs using port $PORT: $PIDS"
    kill -9 $PIDS
fi
```

Make the script executable:

```bash
chmod +x /home/bjorn/Bjorn/kill_port_8000.sh
```


##### 7.3: USB Gadget Configuration

Modify `/boot/firmware/cmdline.txt`:

```bash
sudo vi /boot/firmware/cmdline.txt
```

Add the following right after `rootwait`:

```
modules-load=dwc2,g_ether
```

Modify `/boot/firmware/config.txt`:

```bash
sudo vi /boot/firmware/config.txt
```

Add at the end of the file:

```
dtoverlay=dwc2
```

Create the USB gadget script:

```bash
sudo vi /usr/local/bin/usb-gadget.sh
```

Add the following content:

```bash
#!/bin/bash
set -e

modprobe libcomposite
cd /sys/kernel/config/usb_gadget/
mkdir -p g1
cd g1

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "Pi Zero USB" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM network" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

mkdir -p functions/ecm.usb0

# Check for existing symlink and remove if necessary
if [ -L configs/c.1/ecm.usb0 ]; then
    rm configs/c.1/ecm.usb0
fi
ln -s functions/ecm.usb0 configs/c.1/

# Ensure the device is not busy before listing available USB device controllers
max_retries=10
retry_count=0

while ! ls /sys/class/udc > UDC 2>/dev/null; do
    if [ $retry_count -ge $max_retries ]; then
        echo "Error: Device or resource busy after $max_retries attempts."
        exit 1
    fi
    retry_count=$((retry_count + 1))
    sleep 1
done

# Check if the usb0 interface is already configured
if ! ip addr show usb0 | grep -q "172.20.2.1"; then
    ifconfig usb0 172.20.2.1 netmask 255.255.255.0
else
    echo "Interface usb0 already configured."
fi
```

Make the script executable:

```bash
sudo chmod +x /usr/local/bin/usb-gadget.sh
```

Create the systemd service:

```bash
sudo vi /etc/systemd/system/usb-gadget.service
```

Add:

```ini
[Unit]
Description=USB Gadget Service
After=network.target

[Service]
ExecStartPre=/sbin/modprobe libcomposite
ExecStart=/usr/local/bin/usb-gadget.sh
Type=simple
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Configure `usb0`:

```bash
sudo vi /etc/network/interfaces
```

Add:

```ini
allow-hotplug usb0
iface usb0 inet static
    address 172.20.2.1
    netmask 255.255.255.0
```

Reload the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable systemd-networkd
sudo systemctl enable usb-gadget
sudo systemctl start systemd-networkd
sudo systemctl start usb-gadget
```

You must reboot to be able to use it as a USB gadget (with ip)
###### Windows PC Configuration

Set the static IP address on your Windows PC:

- **IP Address**: `172.20.2.2`
- **Subnet Mask**: `255.255.255.0`
- **Default Gateway**: `172.20.2.1`
- **DNS Servers**: `8.8.8.8`, `8.8.4.4`

---

[↖️](#table-of-contents) 
## Running Bjorn

### Manual Start

To manually start Bjorn (without the service, ensure the service is  stopped « sudo systemctl stop bjorn.service »):

```bash
cd /home/bjorn/Bjorn

# Run Bjorn
sudo python Bjorn.py
```


### Service Control

Control the Bjorn service:

```bash
# Start Bjorn
sudo systemctl start bjorn.service

# Stop Bjorn
sudo systemctl stop bjorn.service

# Check status
sudo systemctl status bjorn.service

# View logs
sudo journalctl -u bjorn.service
```

### Fresh Start

To reset Bjorn to a clean state:

```bash
sudo rm -rf /home/bjorn/Bjorn/config/*.json \
    /home/bjorn/Bjorn/data/*.csv \
    /home/bjorn/Bjorn/data/*.log \
    /home/bjorn/Bjorn/data/output/data_stolen/* \
    /home/bjorn/Bjorn/data/output/crackedpwd/* \
    /home/bjorn/Bjorn/config/* \
    /home/bjorn/Bjorn/data/output/scan_results/* \
    /home/bjorn/Bjorn/__pycache__ \
    /home/bjorn/Bjorn/config/__pycache__ \
    /home/bjorn/Bjorn/data/__pycache__ \
    /home/bjorn/Bjorn/actions/__pycache__ \
    /home/bjorn/Bjorn/resources/__pycache__ \
    /home/bjorn/Bjorn/web/__pycache__ \
    /home/bjorn/Bjorn/*.log \
    /home/bjorn/Bjorn/resources/waveshare_epd/__pycache__ \
    /home/bjorn/Bjorn/data/logs/* \
    /home/bjorn/Bjorn/data/output/vulnerabilities/* \
    /home/bjorn/Bjorn/data/logs/*

```

Everything will be recreated automatically at the next launch of Bjorn.

---

[↖️](#table-of-contents) 
## Important Configuration Files

### Shared Configuration (`shared_config.json`)

Defines various settings for Bjorn, including:

- Boolean settings (`manual_mode`, `websrv`, `debug_mode`, etc.).
- Time intervals and delays.
- Network settings.
- Port lists and blacklists.
These settings are accessible on the webpage.

### Actions Configuration (`actions.json`)

Lists the actions to be performed by Bjorn, including (dynamically generated with the content of the folder):

- Module and class definitions.
- Port assignments.
- Parent-child relationships.
- Action status definitions.

---

[↖️](#table-of-contents) 
## Known Issues and Troubleshooting

### Current Development Issues

#### 1. Long Runtime Issue

- **Problem**: `OSError: [Errno 24] Too many open files`
- **Status**: Partially resolved with system limits configuration.
- **Workaround**: Implemented file descriptor limits increase.
- **Monitoring**: Check open files with `lsof -p $(pgrep -f Bjorn.py) | wc -l`
- At the moment the logs show periodically this information as (FD : XXX)

### Troubleshooting Steps

#### 1. Service Issues

```bash
# Check service status
sudo systemctl status bjorn.service

# View detailed logs
sudo journalctl -u bjorn.service -f

# Check port 8000 usage
sudo lsof -i :8000
```

#### 2. Display Issues

```bash
# Verify SPI devices
ls /dev/spi*

# Check user permissions
sudo usermod -a -G spi,gpio bjorn
```

#### 3. Network Issues

```bash
# Check network interfaces
ip addr show

# Test USB gadget interface
ip link show usb0
```

#### 4. Permission Issues

```bash
# Fix ownership
sudo chown -R bjorn:bjorn /home/bjorn/Bjorn

# Fix permissions
sudo chmod -R 755 /home/bjorn/Bjorn
```

---

[↖️](#table-of-contents) 
## E-Paper Display Support

Currently hardcoded for the 2.13-inch V2 & V4 e-Paper HAT. 
My program automatically detect the screen model and adapt the python expressions into my code.

For other versions:
- As i dont have the v1 and v3 to validate my algorithm, i just hope it will work properly.

### Ghosting removed ! 🍾
In my journey to make Bjorn work with the different screen versions, I struggled, hacking several parameters and found out that it was possible to remove the ghosting of screens! I let you see this, I think this method will be very useful for all other projects with the e-paper screen!

---

[↖️](#table-of-contents) 
## Development Guidelines

### Adding New Actions

1. Create a new action file in `actions/`.
2. Implement required methods:
   - `__init__(self, shared_data)`
   - `execute(self, ip, port, row, status_key)`
3. Add the action to `actions.json`.
4. Follow existing action patterns.

### Testing

1. Create a test environment.
2. Use an isolated network.
3. Follow ethical guidelines.
4. Document test cases.

---

[↖️](#table-of-contents) 
## Web Interface

- **Access**: `http://[device-ip]:8000`
- **Features**:
  - Real-time monitoring with a console.
  - Configuration management.
  - Viewing results. (Credentials and files)
  - System control.

---

[↖️](#table-of-contents) 
## Project Roadmap

### Current Focus

- Stability improvements.
- Bug fixes.
- Service reliability.
- Documentation updates.

### Future Plans

- Additional attack modules.
- Enhanced reporting.
- Improved user interface.
- Extended protocol support.

---

[↖️](#table-of-contents) 
## Contributing

The project welcomes contributions in:

- New attack modules.
- Bug fixes.
- Documentation.
- Feature improvements.

---

[↖️](#table-of-contents) 
## Support and Contact

- **Report Issues**: Via GitHub.
- **Guidelines**:
  - Follow ethical guidelines.
  - Document reproduction steps.
  - Provide logs and context.

---

[↖️](#table-of-contents) 
## Conclusion

Bjorn is a powerful tool designed to perform comprehensive network scanning, vulnerability assessment, and data exfiltration. Its modular design and extensive configuration options allow for flexible and targeted operations. By combining different actions and orchestrating them intelligently, Bjorn can provide valuable insights into network security and help identify and mitigate potential risks.

The e-Paper HAT display and web interface make it easy to monitor and interact with Bjorn, providing real-time updates and status information. With its extensible architecture and customizable actions, Bjorn can be adapted to suit a wide range of security testing and monitoring needs.

## 📫 Contact

- **Author**: infinition
- **GitHub**: [infinition/Bjorn](https://github.com/infinition/Bjorn)

---

## 📜 License

2024 - Bjorn is distributed under the MIT License. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.

---
**Note**: This document is subject to change as the project evolves. Please refer to the GitHub repository for the most recent updates.